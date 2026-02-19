# Nova Sonic Healthcare Call Center

An AI-powered outbound call system for healthcare appointment management. Uses Amazon Nova Sonic 2 speech-to-speech model with AWS Bedrock AgentCore for natural, conversational patient interactions.

## Features

- **Natural speech-to-speech interactions** using Amazon Nova Sonic 2
- **Secure patient authentication** using patient name and last 4 digits of SSN
- **Appointment management** — confirm, cancel, or reschedule with context awareness
- **Health information gathering** for upcoming appointments
- **Escalation to a live agent** with SNS notification
- **Multilingual support** — seamlessly switches to patient's preferred language
- **Low-latency bidirectional communication** via WebSocket with SigV4 authentication

[](docs/old.png)

## Demo

<details>
<summary>Authentication</summary>

![Login](docs/screenshots/auth.png)
</details>

<details>
<summary>Reschedule Appointment</summary>

![Reschedule](docs/screenshots/reschedule.png)
</details>

<details>
<summary>Health Information</summary>

![Health Info](docs/screenshots/healthinfo.png)
</details>

## Prerequisites

- **AWS Account** with appropriate permissions
- **Amazon Bedrock Model Access** — Nova Sonic 2
- **AWS CLI** configured
- **AWS CDK** installed
- **Node.js** 20+ and npm for frontend
- **Python** 3.12+ for backend (3.13 recommended)

## Architecture

![Architecture](docs/image.png)

### AWS Services Used

- **Amazon Bedrock AgentCore** — Runtime for BidiAgent deployment
- **Amazon Cognito** — User authentication and Identity Pool for SigV4 credentials
- **Amazon DynamoDB** — Patient and appointment data storage
- **Amazon SNS** — Escalation notifications

## Patient Conversation Flow

![Patient Conversation Flow](docs/patient-flow.png)

## Tool Architecture

| Tool | Description | Technology |
|------|-------------|------------|
| **authenticate_patient** | Verify patient identity (name + SSN last 4) | DynamoDB query |
| **confirm_appointment** | Confirm existing appointment | DynamoDB update |
| **cancel_appointment** | Cancel appointment with reason | DynamoDB update |
| **find_available_slots** | Query available time slots | DynamoDB query |
| **book_appointment_slot** | Book a specific slot | DynamoDB update |
| **record_health_update** | Capture health information | DynamoDB update |
| **escalate_to_agent** | Flag for human callback | SNS notification |

## Project Structure

```
nova-sonic-hcls-call-center/
├── backend/                    # BidiAgent application code
│   ├── agent.py               # Main BidiAgent entry point
│   ├── Dockerfile             # Container for AgentCore
│   ├── clients/               # AWS service clients
│   ├── tools/                 # Healthcare tools
│   ├── prompts/               # System prompts
│   └── pyproject.toml         # Python dependencies
├── frontend/                   # React application
│   ├── src/
│   │   ├── components/        # UI components
│   │   └── lib/               # WebSocket, audio, auth
│   └── package.json
├── infrastructure/             # CDK infrastructure
│   ├── app.py                 # CDK entry point
│   ├── stacks/                # CDK stacks
│   └── cdk_constructs/        # Modular constructs
└── docs/                       # Documentation and diagrams
```

## Getting Started

See the [Deployment Guide](docs/DEPLOYMENT.md) for step-by-step setup instructions and [cleanup](docs/DEPLOYMENT.md#clean-up).

## Disclaimer

- This is a reference implementation demonstrating Amazon Bedrock AgentCore with Amazon Nova Sonic 2.
- The frontend UI is for demonstration purposes only.
- Before deploying to production, conduct a thorough security review and HIPAA compliance assessment tailored to your organization's requirements.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
