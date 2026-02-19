import { Outlet } from "react-router-dom";
import NavBar from "@/components/Navbar";

export default function Root() {
  return (
    <div className="flex h-screen flex-col bg-surface">
      <NavBar />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
