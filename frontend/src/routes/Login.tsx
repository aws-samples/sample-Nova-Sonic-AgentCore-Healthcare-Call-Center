import { useEffect } from "react";

import { Authenticator, useAuthenticator, View } from "@aws-amplify/ui-react";
import "@aws-amplify/ui-react/styles.css";

import { useNavigate, useLocation } from "react-router";

export function Login() {
  const { route } = useAuthenticator((context) => [context.route]);
  const location = useLocation();
  const navigate = useNavigate();
  const from = location.state?.from?.pathname || "/";
  useEffect(() => {
    if (route === "authenticated") {
      navigate(from, { replace: true });
    }
  }, [route, navigate, from]);
  return (
    <View className="auth-wrapper min-h-screen bg-surface">
      <Authenticator hideSignUp={true} />
    </View>
  );
}
