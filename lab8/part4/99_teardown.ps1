Set-Location $PSScriptRoot
$region = "us-east-1"
New-Item -ItemType Directory -Force results | Out-Null

# 0. save the evidence first
aws logs tail /aws/lambda/lab8-alert --since 3h --region $region | Out-File -Encoding utf8 results\alert_lambda_log.txt
(Get-Date).ToUniversalTime().ToString("o") | Out-File -Encoding ascii results\deleted_at.txt

# 1. delete in order: mapping, Lambda, Firehose, Kinesis, SNS, log group, roles
$uuids = (aws lambda list-event-source-mappings --function-name lab8-alert --region $region --query "EventSourceMappings[].UUID" --output text) -split "\s+" | Where-Object { $_ }
foreach ($u in $uuids) { aws lambda delete-event-source-mapping --uuid $u --region $region | Out-Null }
aws lambda delete-function --function-name lab8-alert --region $region
aws firehose delete-delivery-stream --delivery-stream-name lab8-payments-firehose --region $region
aws kinesis delete-stream --stream-name lab8-payments-stream --enforce-consumer-deletion --region $region
aws sns delete-topic --topic-arn arn:aws:sns:us-east-1:594559484590:lab8-alerts --region $region
aws logs delete-log-group --log-group-name /aws/lambda/lab8-alert --region $region
aws iam delete-role-policy --role-name lab8-firehose-role --policy-name lab8-firehose-policy
aws iam delete-role --role-name lab8-firehose-role
aws iam detach-role-policy --role-name lab8-alert-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaKinesisExecutionRole
aws iam delete-role-policy --role-name lab8-alert-lambda-role --policy-name lab8-alert-sns
aws iam delete-role --role-name lab8-alert-lambda-role

# 2. prove that nothing billable is left
Start-Sleep 30
"--- Kinesis streams:";  aws kinesis list-streams --region $region
"--- Firehose streams:"; aws firehose list-delivery-streams --region $region
"--- Lambda functions:"; aws lambda list-functions --region $region --query "Functions[].FunctionName" --output text
"--- SNS topics:";       aws sns list-topics --region $region --query "Topics[].TopicArn" --output text
"--- lab8 IAM roles:";   aws iam list-roles --query "Roles[?starts_with(RoleName,'lab8-')].RoleName" --output text
