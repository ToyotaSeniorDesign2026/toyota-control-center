import { createBrowserRouter } from "react-router";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Research from "./pages/Research";
import Resources from "./pages/Resources";
import Runs from "./pages/Runs";
import Approvals from "./pages/Approvals";
import Risk from "./pages/Risk";
import Profile from "./pages/Profile";
import UserHome from "./pages/UserHome";
import MyResources from "./pages/MyResources";
import PromotionsEdits from "./pages/PromotionsEdits";
import { LoginPage } from "./pages/LoginPage";

// Create the router with all routes
export const router = createBrowserRouter([
  {
    path: "/login",
    Component: LoginPage,
  },
  {
    path: "/user-home",
    Component: UserHome,
  },
  {
    path: "/my-resources",
    Component: MyResources,
  },
  {
    path: "/promotions-edits",
    Component: PromotionsEdits,
  },
  {
    path: "/",
    Component: Layout,
    children: [
      {
        index: true,
        Component: Dashboard,
      },
      {
        path: "research",
        Component: Research,
      },
      {
        path: "resources",
        Component: Resources,
      },
      {
        path: "runs",
        Component: Runs,
      },
      {
        path: "approvals",
        Component: Approvals,
      },
      {
        path: "risk",
        Component: Risk,
      },
      {
        path: "profile",
        Component: Profile,
      },
      {
        path: "admin",
        Component: () => (
          <div className="p-8">
            <h1 className="text-2xl font-bold text-gray-900">Admin</h1>
            <p className="mt-2 text-gray-600">Coming soon...</p>
          </div>
        ),
      },
    ],
  },
]);