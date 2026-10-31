import os
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

s3 = boto3.client('s3')
ses = boto3.client('sesv2')

def handler(event, context):
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        # Завантаження CSV із S3
        response = s3.get_object(Bucket=bucket, Key=key)
        file_content = response['Body'].read()
        filename = key.split('/')[-1]

        # Формування листа
        msg = MIMEMultipart()
        msg['Subject'] = f"Weekly Report: {filename}"
        msg['From'] = os.environ['SENDER_EMAIL']
        msg['To'] = os.environ['RECIPIENT_EMAIL']

        msg.attach(MIMEText("Вітаємо! Ваш тижневий звіт у додатку.", "plain"))

        att = MIMEApplication(file_content)
        att.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(att)

        # Відправка через SES
        ses.send_email(
            Content={'Raw': {'Data': msg.as_bytes()}}
        )
    return {"statusCode": 200}
