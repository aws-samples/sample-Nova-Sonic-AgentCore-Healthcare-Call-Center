/**
 * Auth Service for AWS Cognito authentication.
 *
 * Provides authentication methods using AWS Amplify Auth
 * and credential retrieval for SigV4 signing.
 */

import {
  signIn,
  signOut,
  fetchAuthSession,
  getCurrentUser,
  type SignInInput,
  type AuthSession,
} from 'aws-amplify/auth';

/**
 * AWS Credentials structure
 */
export interface AWSCredentials {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken?: string;
  expiration?: Date;
}

/**
 * Current user information
 */
export interface CurrentUser {
  userId: string;
  username: string;
  signInDetails?: {
    loginId?: string;
    authFlowType?: string;
  };
}

/**
 * Auth Service class for managing authentication
 */
export class AuthService {
  /**
   * Sign in with username and password.
   *
   * @param username - User's username or email
   * @param password - User's password
   * @returns True if sign in was successful
   */
  static async signIn(username: string, password: string): Promise<boolean> {
    try {
      const input: SignInInput = {
        username,
        password,
      };

      const result = await signIn(input);

      if (result.isSignedIn) {
        console.log('[AuthService] Sign in successful');
        return true;
      }

      // Handle additional challenges if needed
      if (result.nextStep) {
        console.log('[AuthService] Additional step required:', result.nextStep.signInStep);
        // For this simple implementation, we only handle basic sign in
        throw new Error(`Additional authentication step required: ${result.nextStep.signInStep}`);
      }

      return false;

    } catch (error) {
      console.error('[AuthService] Sign in error:', error);
      throw error;
    }
  }

  /**
   * Sign out the current user.
   */
  static async signOut(): Promise<void> {
    try {
      await signOut();
      console.log('[AuthService] Sign out successful');
    } catch (error) {
      console.error('[AuthService] Sign out error:', error);
      throw error;
    }
  }

  /**
   * Get the current authenticated user.
   *
   * @returns Current user info or null if not authenticated
   */
  static async getCurrentUser(): Promise<CurrentUser | null> {
    try {
      const user = await getCurrentUser();
      return {
        userId: user.userId,
        username: user.username,
        signInDetails: user.signInDetails,
      };
    } catch (error) {
      // User is not authenticated
      console.log('[AuthService] No authenticated user');
      return null;
    }
  }

  /**
   * Check if a user is currently authenticated.
   *
   * @returns True if user is authenticated
   */
  static async isAuthenticated(): Promise<boolean> {
    try {
      const user = await getCurrentUser();
      return !!user;
    } catch {
      return false;
    }
  }

  /**
   * Get AWS credentials for the authenticated user.
   *
   * @returns AWS credentials or null if not authenticated
   */
  static async getCredentials(): Promise<AWSCredentials | null> {
    try {
      const session = await fetchAuthSession();

      if (!session.credentials) {
        console.warn('[AuthService] No credentials in session');
        return null;
      }

      return {
        accessKeyId: session.credentials.accessKeyId,
        secretAccessKey: session.credentials.secretAccessKey,
        sessionToken: session.credentials.sessionToken,
        expiration: session.credentials.expiration,
      };

    } catch (error) {
      console.error('[AuthService] Error fetching credentials:', error);
      return null;
    }
  }

  /**
   * Get the full auth session.
   *
   * @returns Auth session or null if not authenticated
   */
  static async getSession(): Promise<AuthSession | null> {
    try {
      const session = await fetchAuthSession();
      return session;
    } catch (error) {
      console.error('[AuthService] Error fetching session:', error);
      return null;
    }
  }

  /**
   * Get the ID token for the current user.
   *
   * @returns ID token string or null
   */
  static async getIdToken(): Promise<string | null> {
    try {
      const session = await fetchAuthSession();
      return session.tokens?.idToken?.toString() ?? null;
    } catch (error) {
      console.error('[AuthService] Error fetching ID token:', error);
      return null;
    }
  }

  /**
   * Get the access token for the current user.
   *
   * @returns Access token string or null
   */
  static async getAccessToken(): Promise<string | null> {
    try {
      const session = await fetchAuthSession();
      return session.tokens?.accessToken?.toString() ?? null;
    } catch (error) {
      console.error('[AuthService] Error fetching access token:', error);
      return null;
    }
  }

  /**
   * Force refresh the auth session.
   *
   * @returns True if refresh was successful
   */
  static async refreshSession(): Promise<boolean> {
    try {
      // Amplify v6 automatically handles token refresh
      // Forcing a new fetch will trigger refresh if needed
      const session = await fetchAuthSession({ forceRefresh: true });
      return !!session.credentials;
    } catch (error) {
      console.error('[AuthService] Error refreshing session:', error);
      return false;
    }
  }
}

// Export singleton instance methods for convenience
export const auth = {
  signIn: AuthService.signIn,
  signOut: AuthService.signOut,
  getCurrentUser: AuthService.getCurrentUser,
  isAuthenticated: AuthService.isAuthenticated,
  getCredentials: AuthService.getCredentials,
  getSession: AuthService.getSession,
  getIdToken: AuthService.getIdToken,
  getAccessToken: AuthService.getAccessToken,
  refreshSession: AuthService.refreshSession,
};
