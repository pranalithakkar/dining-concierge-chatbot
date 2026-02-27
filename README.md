# Dining Concierge Chatbot - HW1

A serverless dining concierge chatbot built on AWS for the Cloud Computing course at NYU.

## Live Demo
**Website URL:** http://dining-concierge-bot-pt2611-ym3470.s3-website-us-east-1.amazonaws.com/chat.html

## Demo Video
[![Watch Demo](https://img.youtube.com/vi/tomOmhIH_TQ/0.jpg)](https://www.youtube.com/watch?v=tomOmhIH_TQ)

## Architecture
- **Frontend:** S3 Static Website
- **API:** API Gateway + Lambda (LF0)
- **NLU:** Amazon Lex
- **Validation:** Lambda (LF1)
- **Queue:** Amazon SQS
- **Search:** OpenSearch
- **Database:** DynamoDB
- **Email:** Amazon SES
- **Worker:** Lambda (LF2)

## Supported Cuisines
Chinese, Italian, Japanese, Mexican, Indian

## Supported Location
Manhattan, NYC

## Repository Structure
- `frontend/` - S3 static website files
- `lambda-functions/` - LF0, LF1, LF2 Lambda function code
- `other-scripts/` - OpenSearch data loading script