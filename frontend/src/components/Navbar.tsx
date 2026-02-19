import { useAuthenticator } from "@aws-amplify/ui-react";
import { IconLogout } from "@tabler/icons-react";
import Avatar from "@/components/Avatar";
import { useNavigate } from "react-router-dom";

declare global {
  interface Window {
    APP_CONFIG: Record<string, string>;
  }
}

export default function Navbar() {
  const { signOut } = useAuthenticator((context) => [context.user]);
  const navigate = useNavigate();

  const handleSignOut = async () => {
    try {
      await signOut();
      navigate("/");
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <nav className="flex w-full items-center justify-between bg-surface-elevated px-5 py-3 shadow-lg shadow-black/20">
      <div className="flex items-center gap-3">
        <div className="h-7 w-7 rounded-lg bg-accent/15 flex items-center justify-center">
          <svg
            className="h-4 w-4 text-accent"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
            />
          </svg>
        </div>
        <h1 className="font-display text-base font-semibold tracking-tight text-text-primary">
          Healthcare Voice Assistant
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <Avatar size="small" avatarType="user" />
        <button
          onClick={handleSignOut}
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-white/5 hover:text-text-primary"
        >
          <IconLogout size={14} />
          <span>Sign out</span>
        </button>
      </div>
    </nav>
  );
}
