import { RouterProvider } from "react-router";
import { router } from "./routes";
import { UserProvider } from "./contexts/UserContext";
import { AIProvider } from "./contexts/AIContext";
import { CalendarProvider } from "./contexts/CalendarContext";
import { CalendarOverlay } from "./components/CalendarOverlay";

function App() {
  return (
    <UserProvider>
      <AIProvider>
        <CalendarProvider>
          <RouterProvider router={router} />
          <CalendarOverlay />
        </CalendarProvider>
      </AIProvider>
    </UserProvider>
  );
}

export default App;
