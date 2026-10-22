# Architecture

## Deployed

```mermaid
flowchart LR
  U["Engineer<br/>agentcore invoke"] -->|"SigV4<br/>IAM inbound auth"| E
  subgraph RT["AgentCore Runtime · isolated session microVM"]
    direction LR
    E["BedrockAgentCoreApp<br/>entrypoint"] --> A["Strands agent<br/>3 read-only tools"]
  end
  A <-->|"ConverseStream"| M["Amazon Bedrock<br/>Nova 2 Lite"]
  subgraph APIS["AWS read APIs · called under the execution role"]
    direction TB
    CW["CloudWatch<br/>DescribeAlarms"]
    EC["EC2<br/>DescribeInstances"]
    CE["Cost Explorer<br/>GetCostAndUsage"]
  end
  A -->|"alarm_state"| CW
  A -->|"ec2_inventory"| EC
  A -->|"yesterday_spend"| CE
  subgraph CTRL["Controls"]
    direction TB
    R["Execution role · CDK<br/>allow: 3 read actions<br/>deny: every model but Nova 2 Lite"]
    O["CloudWatch Logs<br/>+ OpenTelemetry"]
  end
  RT -.- CTRL
```

## One request

```mermaid
sequenceDiagram
  autonumber
  participant U as Engineer (CLI)
  participant RT as AgentCore Runtime
  participant AG as Strands agent
  participant BR as Bedrock Nova 2 Lite
  participant AWS as CloudWatch, EC2, Cost Explorer
  U->>RT: InvokeAgentRuntime, SigV4, session id
  RT->>AG: invoke(payload, context)
  AG->>BR: prompt + three tool schemas
  BR-->>AG: call alarm_state, ec2_inventory, yesterday_spend
  AG->>AWS: three read calls under the execution role
  AWS-->>AG: JSON results, or AccessDenied
  AG->>BR: tool results
  BR-->>AG: brief text
  RT-->>U: ops brief
```

## Deploy path

`agentcore deploy` synthesizes the CDK app into a CloudFormation template, bootstraps the account if needed (staging bucket and deploy roles), uploads the code zip to the staging bucket, and deploys the stack `AgentCore-opsbriefagentcore-default`, which creates the Runtime, its execution role and its log group.

A note for deploying into someone else's account: CDK's default bootstrap roles are broad. In a client account, bootstrap with `--trust` limited to the deploying account and a permissions boundary, or deploy from the pipeline role they already run.

## Target (dashed boxes are designed, not deployed)

```mermaid
flowchart LR
  SCH["EventBridge Scheduler"] --> RT3
  C2["Caller"] -->|"JWT"| RT3["AgentCore Runtime<br/>agent"]
  RT3 -->|"MCP + JWT"| GW["Gateway"]
  GW --> PO["Policy · Cedar<br/>default deny"]
  GW --> LT["Lambda target<br/>3 read tools<br/>own scoped role"]
  LT --> APIs["CloudWatch, EC2,<br/>Cost Explorer"]
  RT3 <--> MEM["Memory"]
  RT3 -.-> ID["Identity<br/>workload identity"]
  RT3 --> SES["SES delivery"]
  classDef designed stroke-dasharray: 6 4
  class SCH,GW,PO,LT,MEM,ID,SES designed
```

The change that matters most: once the tools sit behind Gateway in a Lambda target, the three read permissions move to that target's role. The agent's own execution role keeps only model invocation and telemetry. The agent can no longer reach AWS directly; it can only ask the Gateway, and Policy decides whether to let it.

| Component | Planned configuration | Main risk it addresses or introduces |
|---|---|---|
| Gateway | Lambda target, Cognito JWT inbound, pinned client and audience | One authenticated, audited entry point for tools |
| Policy | Cedar, default deny, permit the three read tools for this agent only | Excessive agency, enforced outside the prompt |
| Memory | Short-term events plus a narrow summary strategy, namespaced by verified actor ID | Introduces memory poisoning; extraction limited to tool results |
| Identity | Workload identity; token vault only if a third-party API is added | Keeps outbound credentials out of agent code |
