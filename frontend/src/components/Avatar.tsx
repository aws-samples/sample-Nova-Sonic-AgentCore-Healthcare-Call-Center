import { IconMessageChatbot, IconUser } from "@tabler/icons-react";
import { useAuthenticator } from "@aws-amplify/ui-react";

type AvatarProps = {
  avatarType: "user" | "bot";
  size: null | "user" | "small";
};

export default function Avatar({ avatarType, size }: AvatarProps) {
  const {
    user: { username },
  } = useAuthenticator((context) => [context.user]);

  const sizeVariants = {
    default: "h-10 w-10 leading-10 text-lg",
    small: "h-7 w-7 leading-7 text-xs",
  };

  const sizeClasses =
    size !== null
      ? sizeVariants[size as keyof typeof sizeVariants]
      : sizeVariants.default;

  return (
    <div
      className={`${sizeClasses} flex flex-none select-none rounded-full
        ${
          avatarType && avatarType === "bot"
            ? "mr-2 bg-accent/20 ring-1 ring-accent/30"
            : "bg-surface-accent text-text-primary ring-1 ring-accent/20"
        }`}
    >
      {avatarType === "user" && (
        <span className="flex-1 text-center font-semibold">
          {username?.charAt(0).toUpperCase()}
        </span>
      )}

      {avatarType === "bot" && (
        <IconMessageChatbot className="m-auto stroke-accent" size={16} />
      )}

      {!avatarType && (
        <IconUser size={16} className="m-auto stroke-text-secondary" />
      )}
    </div>
  );
}
