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
        <CalendarProvider>
          <JobRunProvider>
            <RouterProvider router={router} />
            <CalendarOverlay />
          </JobRunProvider>
        </CalendarProvider>
      </AIProvider>
    </UserProvider>
  );
}

export default App;
