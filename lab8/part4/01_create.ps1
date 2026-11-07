param([Parameter(Mandatory = $true)][string]$Email)
Set-Location $PSScriptRoot
$region = "us-east-1"
$bucket = "lab8-payments-594559484590"
$stream = "lab8-payments-stream"
New-Item -ItemType Directory -Force tmp, results | Out-Null

function Invoke-Aws {
  & aws @args
  if ($LASTEXITCODE -ne 0) { throw "aws command failed: $($args -join ' ')" }
}

(Get-Date).ToUniversalTime().ToString("o") | Out-File -Encoding ascii results\created_at.txt

# 1. Kinesis stream, one provisioned shard
Invoke-Aws kinesis create-stream --stream-name $stream --shard-count 1 --region $region
Invoke-Aws kinesis wait stream-exists --stream-name $stream --region $region
$streamArn = aws kinesis describe-stream-summary --stream-name $stream --region $region --query StreamDescriptionSummary.StreamARN --output text
Write-Host "Kinesis ready: $streamArn"

# 2. SNS topic and email subscription
$topicArn = aws sns create-topic --name lab8-alerts --region $region --query TopicArn --output text
Invoke-Aws sns subscribe --topic-arn $topicArn --protocol email --notification-endpoint $Email --region $region
Write-Host "SNS topic: $topicArn  (confirm the subscription in your email)"

# 3. Firehose role: read the stream, write the bucket
@"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"firehose.amazonaws.com"},"Action":"sts:AssumeRole"}]}
"@ | Set-Content -Encoding ascii tmp\firehose-trust.json
@"
{"Version":"2012-10-17","Statement":[
{"Effect":"Allow","Action":["kinesis:DescribeStream","kinesis:GetShardIterator","kinesis:GetRecords","kinesis:ListShards"],"Resource":"$streamArn"},
{"Effect":"Allow","Action":["s3:AbortMultipartUpload","s3:GetBucketLocation","s3:GetObject","s3:ListBucket","s3:ListBucketMultipartUploads","s3:PutObject"],"Resource":["arn:aws:s3:::$bucket","arn:aws:s3:::$bucket/streamed/*"]}]}
"@ | Set-Content -Encoding ascii tmp\firehose-policy.json
$fhRoleArn = aws iam create-role --role-name lab8-firehose-role --assume-role-policy-document file://tmp/firehose-trust.json --query Role.Arn --output text
if ($LASTEXITCODE -ne 0) { throw "could not create lab8-firehose-role" }
Invoke-Aws iam put-role-policy --role-name lab8-firehose-role --policy-name lab8-firehose-policy --policy-document file://tmp/firehose-policy.json

# 4. Lambda role: Kinesis read (managed policy) and sns:Publish on one topic
@"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
"@ | Set-Content -Encoding ascii tmp\lambda-trust.json
@"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sns:Publish","Resource":"$topicArn"}]}
"@ | Set-Content -Encoding ascii tmp\lambda-sns-policy.json
$lrRoleArn = aws iam create-role --role-name lab8-alert-lambda-role --assume-role-policy-document file://tmp/lambda-trust.json --query Role.Arn --output text
if ($LASTEXITCODE -ne 0) { throw "could not create lab8-alert-lambda-role" }
Invoke-Aws iam attach-role-policy --role-name lab8-alert-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaKinesisExecutionRole
Invoke-Aws iam put-role-policy --role-name lab8-alert-lambda-role --policy-name lab8-alert-sns --policy-document file://tmp/lambda-sns-policy.json
Write-Host "Waiting 20 s for the new roles to propagate..."
Start-Sleep 20

# 5. Firehose: Kinesis -> S3, JSON, 60 s buffer
@"
{
  "DeliveryStreamName": "lab8-payments-firehose",
  "DeliveryStreamType": "KinesisStreamAsSource",
  "KinesisStreamSourceConfiguration": { "KinesisStreamARN": "$streamArn", "RoleARN": "$fhRoleArn" },
  "ExtendedS3DestinationConfiguration": {
    "RoleARN": "$fhRoleArn",
    "BucketARN": "arn:aws:s3:::$bucket",
    "Prefix": "streamed/dt=!{timestamp:yyyy-MM-dd}/",
    "ErrorOutputPrefix": "streamed-errors/!{firehose:error-output-type}/dt=!{timestamp:yyyy-MM-dd}/",
    "BufferingHints": { "SizeInMBs": 1, "IntervalInSeconds": 60 },
    "CompressionFormat": "UNCOMPRESSED"
  }
}
"@ | Set-Content -Encoding ascii tmp\firehose.json
$created = $false
for ($i = 1; ($i -le 6) -and (-not $created); $i++) {
  aws firehose create-delivery-stream --cli-input-json file://tmp/firehose.json --region $region
  if ($LASTEXITCODE -eq 0) { $created = $true } else { Write-Host "Role not ready yet, retrying in 15 s"; Start-Sleep 15 }
}
if (-not $created) { throw "Firehose was not created" }
do {
  $st = aws firehose describe-delivery-stream --delivery-stream-name lab8-payments-firehose --region $region --query DeliveryStreamDescription.DeliveryStreamStatus --output text
  Write-Host "Firehose status: $st"
  if ($st -ne "ACTIVE") { Start-Sleep 10 }
} while ($st -ne "ACTIVE")

# 6. Alert Lambda reading the same stream
Compress-Archive -Path alert_lambda.py -DestinationPath tmp\alert.zip -Force
@"
{"Variables":{"TOPIC_ARN":"$topicArn","MIN_EVENTS":"20","THRESHOLD":"0.10"}}
"@ | Set-Content -Encoding ascii tmp\lambda-env.json
$ok = $false
for ($i = 1; ($i -le 6) -and (-not $ok); $i++) {
  aws lambda create-function --function-name lab8-alert --runtime python3.12 --handler alert_lambda.handler --role $lrRoleArn --zip-file fileb://tmp/alert.zip --timeout 30 --memory-size 128 --environment file://tmp/lambda-env.json --region $region
  if ($LASTEXITCODE -eq 0) { $ok = $true } else { Write-Host "Role not ready yet, retrying in 15 s"; Start-Sleep 15 }
}
if (-not $ok) { throw "Lambda was not created" }
Invoke-Aws lambda wait function-active-v2 --function-name lab8-alert --region $region
Invoke-Aws lambda create-event-source-mapping --function-name lab8-alert --event-source-arn $streamArn --starting-position LATEST --batch-size 500 --maximum-batching-window-in-seconds 5 --region $region
do {
  $st = aws lambda list-event-source-mappings --function-name lab8-alert --region $region --query "EventSourceMappings[0].State" --output text
  Write-Host "Event source mapping: $st"
  if ($st -ne "Enabled") { Start-Sleep 10 }
} while ($st -ne "Enabled")
Write-Host "DONE. Pipeline is ready. Confirm the SNS email, then start the producer."
