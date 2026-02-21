import { RouterProvider } from "react-router";
import { router } from "./routes";
import { UserProvider } from "./contexts/UserContext";
import { AIProvider } from "./contexts/AIContext";

function App() {
  return (
    <UserProvider>
      <AIProvider>
        <RouterProvider router={router} />
      </AIProvider>
    </UserProvider>
  );
}

export default App;