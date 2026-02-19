/**
 * Patient API for Healthcare Voice Assistant
 *
 * Fetches patient data from DynamoDB using Cognito Identity Pool credentials.
 */

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { fetchAuthSession } from "aws-amplify/auth";

const env = window.APP_CONFIG || import.meta.env;

export interface Patient {
  patientId: string;
  name: string;
  ssn4: string;
}

/**
 * Fetch all patients from DynamoDB.
 * Uses Cognito authenticated credentials via Amplify's fetchAuthSession.
 */
export async function fetchPatients(): Promise<Patient[]> {
  const tableName = env.VITE_PATIENTS_TABLE || "nova-healthcare-patients";
  const region = env.VITE_AWS_REGION || "us-east-1";

  const session = await fetchAuthSession();
  const credentials = session.credentials;
  if (!credentials) {
    throw new Error("No authenticated credentials available");
  }

  const client = DynamoDBDocumentClient.from(
    new DynamoDBClient({ region, credentials })
  );

  const result = await client.send(
    new ScanCommand({ TableName: tableName })
  );

  const items = result.Items || [];

  return items.map((item) => ({
    patientId: item.PatientId as string,
    name: `${item.FirstName} ${item.LastName}`,
    ssn4: item.SSNLast4 as string,
  }));
}
