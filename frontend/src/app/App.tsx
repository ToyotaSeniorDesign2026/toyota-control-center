import { RouterProvider } from "react-router";
import { router } from "./routes";
import { UserProvider } from "./contexts/UserContext";
import { AIProvider } from "./contexts/AIContext";
import { CalendarProvider } from "./contexts/CalendarContext";
import { JobRunProvider } from "./contexts/JobRunContext";
import { CalendarOverlay } from "./components/CalendarOverlay";

function App() {
  return (
    <UserProvider>
      <AIProvider>
        <JobRunProvider>
          <CalendarProvider>
            <RouterProvider router={router} />
            <CalendarOverlay />
          </CalendarProvider>
        </JobRunProvider>
      </AIProvider>
    </UserProvider>
  );
}

export default App;
