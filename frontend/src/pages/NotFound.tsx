import { Compass } from "lucide-react";
import { Button, Empty, usePageTitle } from "../components/ui";

export default function NotFound() {
  usePageTitle("Page not found");
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <Empty icon={<Compass size={26} />} title="This page doesn't exist" action={<Button variant="primary" to="/">Back to home</Button>}>
        The link may be old or mistyped.
      </Empty>
    </div>
  );
}
