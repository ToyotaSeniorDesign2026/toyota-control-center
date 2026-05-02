import { createBrowserRouter } from "react-router";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Research from "./pages/Research";
import Jobs from "./pages/Jobs";
import Runs from "./pages/Runs";
import Approvals from "./pages/Approvals";
import Risk from "./pages/Risk";
import Profile from "./pages/Profile";
import UserHome from "./pages/UserHome";
import MyJobs from "./pages/MyJobs";
import PendingApprovals from "./pages/PendingApprovals";
import RunningJobs from "./pages/RunningJobs";
import PromotionsEdits from "./pages/PromotionsEdits";
import Promotions from "./pages/Promotions";
import Edits from "./pages/Edits";
import Forms from "./pages/Forms";
import PreBuiltForms from "./pages/PreBuiltForms";
import MySavedForms from "./pages/MySavedForms";
import ExcelReport from "./pages/ExcelReport";
import SQLJob from "./pages/SQLJob";
import PowerPoint from "./pages/PowerPoint";
import { LoginPage } from "./pages/LoginPage";
import CalendarPage from "./pages/Calendar";
import RequiredActionForm from "./pages/RequiredActionForm";
import RequiredActions from "./pages/RequiredActions";
import CreateJob from "./pages/CreateJob";
import Connectors from "./pages/Connectors";
<<<<<<< HEAD
import Admin from "./pages/Admin";
=======
>>>>>>> polishing-agent-chat

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
    path: "/my-jobs",
    Component: MyJobs,
  },
  {
    path: "/jobs/my-jobs",
    Component: MyJobs,
  },
  {
    path: "/jobs/pending-approvals",
    Component: PendingApprovals,
  },
  {
    path: "/jobs/running-jobs",
    Component: RunningJobs,
  },
  {
    path: "/promotions-edits",
    Component: PromotionsEdits,
  },
  {
    path: "/promotions-edits/promotions",
    Component: Promotions,
  },
  {
    path: "/promotions-edits/edits",
    Component: Edits,
  },
  {
    path: "/forms",
    Component: Forms,
  },
  {
    path: "/forms/pre-built-forms",
    Component: PreBuiltForms,
  },
  {
    path: "/forms/saved-templates",
    Component: MySavedForms,
  },
  {
    path: "/forms/my-saved-forms",
    Component: MySavedForms,
  },
  {
    path: "/excel-report",
    Component: ExcelReport,
  },
  {
    path: "/sql-job",
    Component: SQLJob,
  },
  {
    path: "/powerpoint",
    Component: PowerPoint,
  },
  {
    path: "/calendar",
    Component: CalendarPage,
  },
  {
    path: "/required-actions/:actionId",
    Component: RequiredActionForm,
  },
  {
    path: "/required-actions",
    Component: RequiredActions,
  },
  {
    path: "/create-job",
    Component: CreateJob,
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
        path: "jobs",
        Component: Jobs,
      },
      {
        path: "connectors",
        Component: Connectors,
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
        Component: Admin,
      },
    ],
  },
]);
