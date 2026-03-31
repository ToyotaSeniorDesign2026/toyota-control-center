import { MessageSquare, X, Send, Plus, Loader2, Play, Server, Clock3 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useJobRuns, type ChatJobDraft } from "../contexts/JobRunContext";
import {
  listMcpServers,
  requestOpenAIChat,
  type MCPServerSummary,
  type OpenAIChatMessage,
} from "../lib/controlCenterApi";

interface ChatMessage {
  id: string;
  role: "assistant" | "user" | "system";
  content: string;
  timestamp: Date;
  options?: string[];
}

type ChatStep =
  | "chooseJobType"
  | "chooseRunMode"
  | "collectName"
  | "collectEnvironment"
  | "collectSqlMcpServer"
  | "collectDescription"
  | "collectMcpServer"
  | "collectResearchTopic"
  | "collectResearchMaxResults"
  | "collectMcpToolName"
  | "collectMcpPrompt"
  | "collectSchedule"
  | "confirm";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const initialDraft: ChatJobDraft = {
  name: "",
  jobType: "sql",
  environment: "dev",
  oneTime: true,
  description: "",
};

const initialMessages: ChatMessage[] = [
  {
    id: "welcome-1",
    role: "assistant",
    content:
      "I can help you launch a job from chat. I’ll ask a few short questions, create the job if needed, and start the run for you.",
    timestamp: new Date(),
    options: ["SQL", "Excel", "PowerPoint", "MCP Job"],
  },
];

function normalizeChoice(value: string) {
  return value.trim().toLowerCase();
}

function titleForJobType(jobType: ChatJobDraft["jobType"]) {
  switch (jobType) {
    case "sql":
      return "SQL";
    case "excel":
      return "Excel";
    case "powerpoint":
      return "PowerPoint";
    case "mcp":
      return "MCP";
  }
}

function parseEnvironment(input: string): ChatJobDraft["environment"] | null {
  const value = normalizeChoice(input);
  if (value === "dev" || value === "semi-prod" || value === "prod") {
    return value;
  }
  if (value === "semi prod" || value === "staging") {
    return "semi-prod";
  }
  return null;
}

function mapStatusLabel(status: string) {
  switch (status) {
    case "queued":
      return "Queued";
    case "executing":
      return "Executing";
    case "running":
      return "Running";
    case "succeeded":
      return "Succeeded";
    case "failed":
      return "Failed";
    case "stopped":
      return "Stopped";
    default:
      return status;
  }
}

function looksLikeSqlMcpServer(server: MCPServerSummary) {
  return server.tags.some((tag) => ["sql", "database"].includes(tag));
}

function serverLabel(server: MCPServerSummary) {
  return server.display_name?.trim() || server.name;
}

function findMatchingServer(input: string, servers: MCPServerSummary[]) {
  const normalized = normalizeChoice(input);
  return (
    servers.find((server) => {
      const names = [server.name, serverLabel(server)];
      return names.some((name) => normalizeChoice(name) === normalized);
    }) ?? null
  );
}

function extractRequestedSqlServer(input: string, servers: MCPServerSummary[]) {
  const normalized = normalizeChoice(input);
  for (const server of servers) {
    const aliases = [server.name, serverLabel(server)].map(normalizeChoice);
    for (const serverName of aliases) {
      if (
        normalized === serverName ||
        normalized.includes(`switch to ${serverName}`) ||
        normalized.includes(`use ${serverName}`) ||
        normalized.includes(`query ${serverName}`) ||
        normalized.includes(`database ${serverName}`) ||
        normalized.includes(`source ${serverName}`)
      ) {
        return server;
      }
    }
  }
  return null;
}

const AUTH_TOKEN_KEY = "control-center-auth-token";

function getAuthToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY) ?? "u_analyst";
}

export function ChatPanel({ isOpen, onClose }: ChatPanelProps) {
  const { launchJobFromChat, error } = useJobRuns();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [step, setStep] = useState<ChatStep>("chooseJobType");
  const [draft, setDraft] = useState<ChatJobDraft>(initialDraft);
  const [isLaunching, setIsLaunching] = useState(false);
  const [mcpServers, setMcpServers] = useState<MCPServerSummary[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void listMcpServers(getAuthToken())
      .then((response) => setMcpServers(response.items))
      .catch(() => setMcpServers([]));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLaunching]);

  const generalMcpServerNames = useMemo(
    () => mcpServers.filter((server) => !looksLikeSqlMcpServer(server)),
    [mcpServers],
  );
  const sqlMcpServers = useMemo(() => mcpServers.filter(looksLikeSqlMcpServer), [mcpServers]);
  const generalMcpServerLabels = useMemo(() => generalMcpServerNames.map(serverLabel), [generalMcpServerNames]);
  const sqlMcpServerLabels = useMemo(() => sqlMcpServers.map(serverLabel), [sqlMcpServers]);
  const displayServerName = (serverId?: string) => {
    if (!serverId) {
      return "Not set";
    }
    return serverLabel(mcpServers.find((server) => server.name === serverId) ?? { name: serverId, tags: [], allowed_environments: [], active: true });
  };

  const currentPrompt = useMemo(() => {
    switch (step) {
      case "chooseJobType":
        return "Choose the job type you want to run.";
      case "chooseRunMode":
        return `Should I run this ${titleForJobType(draft.jobType)} job once, or save it with a schedule too?`;
      case "collectName":
        return "What should I call this job?";
      case "collectEnvironment":
        return "Which environment should I run it in? Use `dev`, `semi-prod`, or `prod`.";
      case "collectSqlMcpServer":
        return "Which database or approved SQL MCP source should I use?";
      case "collectDescription":
        return `Give me a short description of what this ${titleForJobType(draft.jobType)} job should do.`;
      case "collectMcpServer":
        return "Which MCP server should I use?";
      case "collectResearchTopic":
        return "What research topic should I search for?";
      case "collectResearchMaxResults":
        return "How many papers should I return?";
      case "collectMcpToolName":
        return "If you want a specific MCP tool, name it now. Otherwise say `agent` and I’ll run it as a prompt-driven MCP job.";
      case "collectMcpPrompt":
        return "What prompt should I send to the MCP job?";
      case "collectSchedule":
        return "What schedule should I save for it? Example: `Weekdays at 8:00 AM CT`.";
      case "confirm":
        return "Review the summary below and press `Run now` when it looks right.";
    }
  }, [draft.jobType, step]);

  const appendMessage = (message: ChatMessage) => {
    setMessages((current) => [...current, message]);
  };

  const composeAssistantMessage = async ({
    transcript,
    fallback,
    goal,
    workflowState,
  }: {
    transcript: OpenAIChatMessage[];
    fallback: string;
    goal: string;
    workflowState: Record<string, unknown>;
  }) => {
    try {
      const response = await requestOpenAIChat({
        messages: transcript,
        goal,
        workflow_state: workflowState,
        fallback_response: fallback,
      }, getAuthToken());
      return response.content || fallback;
    } catch {
      return fallback;
    }
  };

  const assistantReply = async ({
    userInput,
    fallback,
    goal,
    workflowState,
    options,
  }: {
    userInput: string;
    fallback: string;
    goal: string;
    workflowState: Record<string, unknown>;
    options?: string[];
  }) => {
    const transcript: OpenAIChatMessage[] = [
      ...messages.map((message) => ({
        role: message.role === "system" ? ("assistant" as const) : message.role,
        content: message.content,
      })),
      {
        role: "user",
        content: userInput,
      },
    ];

    const content = await composeAssistantMessage({
      transcript,
      fallback,
      goal,
      workflowState,
    });

    appendMessage({
      id: `${Date.now()}-assistant`,
      role: "assistant",
      content,
      timestamp: new Date(),
      options,
    });
  };

  const resetConversation = () => {
    setMessages(initialMessages);
    setInputValue("");
    setStep("chooseJobType");
    setDraft(initialDraft);
    setIsLaunching(false);
  };

  const buildConfirmation = (jobDraft: ChatJobDraft) => {
    const lines = [
      `Job type: ${titleForJobType(jobDraft.jobType)}`,
      `Run mode: ${jobDraft.oneTime ? "One-time run" : "Saved job + run now"}`,
      `Name: ${jobDraft.name}`,
      `Environment: ${jobDraft.environment}`,
      `Description: ${jobDraft.description}`,
    ];

    if (jobDraft.jobType === "sql") {
      lines.push(`Database source: ${displayServerName(jobDraft.mcpServer)}`);
    }
    if (jobDraft.jobType !== "sql") {
      lines.push(`MCP server: ${displayServerName(jobDraft.mcpServer)}`);
    }
    if (jobDraft.jobType === "mcp") {
      if (jobDraft.mcpServer === "arxiv-research") {
        lines.push(`Topic: ${jobDraft.topic ?? "Not set"}`);
        lines.push(`Max results: ${jobDraft.maxResults ?? 5}`);
      } else {
        lines.push(`MCP mode: ${jobDraft.mcpToolName ? `Tool ${jobDraft.mcpToolName}` : "Agent prompt"}`);
      }
    }
    if (!jobDraft.oneTime) {
      lines.push(`Schedule: ${jobDraft.schedule ?? "Not set"}`);
    }
    return lines.join("\n");
  };

  const handleConversationTurn = async (rawInput: string) => {
    const trimmed = rawInput.trim();
    if (!trimmed || isLaunching) {
      return;
    }

    appendMessage({
      id: `${Date.now()}-user`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    });
    setInputValue("");

    const value = normalizeChoice(trimmed);

    if (draft.jobType === "sql" && sqlMcpServers.length > 0 && step !== "collectSqlMcpServer") {
      const switchedServer = extractRequestedSqlServer(trimmed, sqlMcpServers);
      if (switchedServer) {
        const nextDraft = { ...draft, mcpServer: switchedServer.name };
        setDraft(nextDraft);
        appendMessage({
          id: `${Date.now()}-assistant-sql-server-updated`,
          role: "assistant",
          content:
            `Updated the SQL data source to ${serverLabel(switchedServer)}.\n\n` +
            `You can keep answering the current question, or press \`Run now\` once the summary looks right.`,
          timestamp: new Date(),
          options: step === "confirm" ? ["Run now", "Start over"] : undefined,
        });
        return;
      }
    }

    if (step === "chooseJobType") {
      const nextJobType: ChatJobDraft["jobType"] | null =
        value === "sql"
          ? "sql"
          : value === "excel"
            ? "excel"
            : value === "powerpoint"
              ? "powerpoint"
              : value === "mcp" || value === "mcp job"
                ? "mcp"
                : null;

      if (!nextJobType) {
        await assistantReply({
          userInput: trimmed,
          fallback: "Pick one of these to get started: SQL, Excel, PowerPoint, or MCP Job.",
          goal: "Ask the user to choose one supported job type.",
          workflowState: { step, draft },
          options: ["SQL", "Excel", "PowerPoint", "MCP Job"],
        });
        return;
      }

      const nextDraft = {
        ...initialDraft,
        ...draft,
        jobType: nextJobType,
        mcpServer: undefined,
        mcpPrompt: undefined,
        mcpToolName: undefined,
        mcpToolArguments: undefined,
        query: undefined,
        topic: undefined,
        maxResults: undefined,
      };
      setDraft(nextDraft);
      setStep("chooseRunMode");
      await assistantReply({
        userInput: trimmed,
        fallback: `Perfect. Should this be a one-time ${titleForJobType(nextJobType)} run, or should I save it and run it now?`,
        goal: "Ask whether the user wants a one-time run or a saved scheduled job that also runs now.",
        workflowState: { step: "chooseRunMode", draft: nextDraft },
        options: ["One-time", "Save and run"],
      });
      return;
    }

    if (step === "chooseRunMode") {
      if (value !== "one-time" && value !== "save and run") {
        await assistantReply({
          userInput: trimmed,
          fallback: "Choose `One-time` or `Save and run`.",
          goal: "Ask the user to choose one of the two supported run modes.",
          workflowState: { step, draft },
          options: ["One-time", "Save and run"],
        });
        return;
      }

      const nextDraft = { ...draft, oneTime: value === "one-time" };
      setDraft(nextDraft);
      setStep("collectName");
      await assistantReply({
        userInput: trimmed,
        fallback: "What should I call this job?",
        goal: "Ask for the job name.",
        workflowState: { step: "collectName", draft: nextDraft },
      });
      return;
    }

    if (step === "collectName") {
      const nextDraft = { ...draft, name: trimmed };
      setDraft(nextDraft);
      setStep("collectEnvironment");
      await assistantReply({
        userInput: trimmed,
        fallback: "Which environment should I use? Choose `dev`, `semi-prod`, or `prod`.",
        goal: "Ask the user to choose the target environment.",
        workflowState: { step: "collectEnvironment", draft: nextDraft },
        options: ["dev", "semi-prod", "prod"],
      });
      return;
    }

    if (step === "collectEnvironment") {
      const environment = parseEnvironment(trimmed);
      if (!environment) {
        await assistantReply({
          userInput: trimmed,
          fallback: "I need one of these environments: `dev`, `semi-prod`, or `prod`.",
          goal: "Ask the user to choose one valid environment.",
          workflowState: { step, draft },
          options: ["dev", "semi-prod", "prod"],
        });
        return;
      }

      const nextDraft = { ...draft, environment };
      setDraft(nextDraft);
      if (draft.jobType === "sql") {
        setStep("collectSqlMcpServer");
        await assistantReply({
          userInput: trimmed,
          fallback:
            sqlMcpServerLabels.length > 0
              ? "Which database or approved SQL MCP source should I use for this SQL job?"
              : "Which SQL MCP server should I use? Type the server name (e.g. `sql-dab` for Control Center Dev, `sql-dab-analytics` for Analytics).",
          goal: "Ask the user to choose the database source by selecting one approved SQL MCP server for the SQL job.",
          workflowState: { step: "collectSqlMcpServer", draft: nextDraft, sql_mcp_servers: sqlMcpServerLabels },
          options: sqlMcpServerLabels.length > 0 ? sqlMcpServerLabels : undefined,
        });
      } else {
        setStep("collectDescription");
        await assistantReply({
          userInput: trimmed,
          fallback: `Describe what this ${titleForJobType(draft.jobType)} job should do.`,
          goal: "Ask for a short description of the job’s purpose.",
          workflowState: { step: "collectDescription", draft: nextDraft },
        });
      }
      return;
    }

    if (step === "collectSqlMcpServer") {
      if (sqlMcpServers.length > 0) {
        const selectedServer = findMatchingServer(trimmed, sqlMcpServers);
        if (!selectedServer) {
          await assistantReply({
            userInput: trimmed,
            fallback: "Choose one of the approved databases below.",
            goal: "Ask the user to choose a supported database source backed by an approved SQL MCP server.",
            workflowState: { step, draft, sql_mcp_servers: sqlMcpServerLabels },
            options: sqlMcpServerLabels,
          });
          return;
        }
        const nextDraft = { ...draft, mcpServer: selectedServer.name };
        setDraft(nextDraft);
        setStep("collectDescription");
        await assistantReply({
          userInput: trimmed,
          fallback: `Using ${serverLabel(selectedServer)}. Describe what data you need from that database.`,
          goal: "Ask for the SQL MCP task description.",
          workflowState: { step: "collectDescription", draft: nextDraft },
        });
        return;
      }

      // Server list unavailable (API unreachable) — accept free-text server name
      const nextDraft = { ...draft, mcpServer: trimmed };
      setDraft(nextDraft);
      setStep("collectDescription");
      await assistantReply({
        userInput: trimmed,
        fallback: `Got it — using \`${trimmed}\`. Describe what data you need from that database.`,
        goal: "Ask for the SQL MCP task description.",
        workflowState: { step: "collectDescription", draft: nextDraft },
      });
      return;
    }

    if (step === "collectDescription") {
      const nextDraft = { ...draft, description: trimmed };
      setDraft(nextDraft);

      if (draft.jobType === "sql") {
        if (draft.oneTime) {
          setStep("confirm");
          appendMessage({
            id: `${Date.now()}-assistant-confirm-sql-mcp`,
            role: "assistant",
            content: buildConfirmation(nextDraft),
            timestamp: new Date(),
            options: ["Run now", "Start over"],
          });
        } else {
          setStep("collectSchedule");
          await assistantReply({
            userInput: trimmed,
            fallback: "What schedule should I save for this SQL MCP job?",
            goal: "Ask the user for the SQL MCP job schedule.",
            workflowState: { step: "collectSchedule", draft: nextDraft },
          });
        }
        return;
      }

      if (draft.jobType === "mcp" || draft.jobType === "excel" || draft.jobType === "powerpoint") {
        setStep("collectMcpServer");
        await assistantReply({
          userInput: trimmed,
          fallback: "Which MCP server should I use for this job?",
          goal: "Ask the user to choose an MCP server.",
          workflowState: { step: "collectMcpServer", draft: nextDraft },
          options: generalMcpServerLabels,
        });
        return;
      }

      if (draft.oneTime) {
        setStep("confirm");
        appendMessage({
          id: `${Date.now()}-assistant-confirm`,
          role: "assistant",
          content: buildConfirmation(nextDraft),
          timestamp: new Date(),
          options: ["Run now", "Start over"],
        });
      } else {
        setStep("collectSchedule");
        await assistantReply({
          userInput: trimmed,
          fallback: "What schedule should I save for it?",
          goal: "Ask the user for the saved schedule.",
          workflowState: { step: "collectSchedule", draft: nextDraft },
        });
      }
      return;
    }

    if (step === "collectMcpServer") {
      const selectedServer = findMatchingServer(trimmed, generalMcpServerNames);
      if (!selectedServer) {
        await assistantReply({
          userInput: trimmed,
          fallback: "Choose one of the supported MCP servers below.",
          goal: "Ask the user to choose a supported MCP server.",
          workflowState: { step, draft },
          options: generalMcpServerLabels,
        });
        return;
      }

      const nextDraft = {
        ...draft,
        mcpServer: selectedServer.name,
        mcpPrompt: draft.mcpPrompt ?? draft.description,
        maxResults: selectedServer.name === "arxiv-research" ? 5 : draft.maxResults,
      };
      setDraft(nextDraft);

      if (draft.jobType === "mcp" && selectedServer.name === "arxiv-research") {
        setStep("collectResearchTopic");
        await assistantReply({
          userInput: trimmed,
          fallback: "What research topic should I search for?",
          goal: "Ask the user for the research topic.",
          workflowState: { step: "collectResearchTopic", draft: nextDraft },
        });
        return;
      }

      if (draft.jobType !== "mcp") {
        if (draft.oneTime) {
          setStep("confirm");
          appendMessage({
            id: `${Date.now()}-assistant-confirm-associated-mcp`,
            role: "assistant",
            content: buildConfirmation(nextDraft),
            timestamp: new Date(),
            options: ["Run now", "Start over"],
          });
        } else {
          setStep("collectSchedule");
          await assistantReply({
            userInput: trimmed,
            fallback: `What schedule should I save for this ${titleForJobType(draft.jobType)} job?`,
            goal: "Ask the user for the saved schedule.",
            workflowState: { step: "collectSchedule", draft: nextDraft },
          });
        }
        return;
      }

      setStep("collectMcpToolName");
      await assistantReply({
        userInput: trimmed,
        fallback:
          "If you need a specific MCP tool, enter it now. Otherwise say `agent` and I’ll let the MCP server handle it from the prompt.",
        goal: "Ask whether the user wants a specific MCP tool or an agent-style prompt.",
        workflowState: { step: "collectMcpToolName", draft: nextDraft },
      });
      return;
    }

    if (step === "collectResearchTopic") {
      const nextDraft = {
        ...draft,
        topic: trimmed,
        description: trimmed,
      };
      setDraft(nextDraft);
      setStep("collectResearchMaxResults");
      await assistantReply({
        userInput: trimmed,
        fallback: "How many papers should I return? Enter a number like `5` or `10`.",
        goal: "Ask the user for the number of research papers to return.",
        workflowState: { step: "collectResearchMaxResults", draft: nextDraft },
      });
      return;
    }

    if (step === "collectResearchMaxResults") {
      const parsed = Number.parseInt(trimmed, 10);
      if (!Number.isFinite(parsed) || parsed <= 0) {
        await assistantReply({
          userInput: trimmed,
          fallback: "Enter a positive number for max results, like `5` or `10`.",
          goal: "Ask the user for a valid positive integer max results value.",
          workflowState: { step, draft },
        });
        return;
      }

      const nextDraft = {
        ...draft,
        maxResults: parsed,
      };
      setDraft(nextDraft);

      if (draft.oneTime) {
        setStep("confirm");
        appendMessage({
          id: `${Date.now()}-assistant-confirm-research`,
          role: "assistant",
          content: buildConfirmation(nextDraft),
          timestamp: new Date(),
          options: ["Run now", "Start over"],
        });
      } else {
        setStep("collectSchedule");
        await assistantReply({
          userInput: trimmed,
          fallback: "What schedule should I save for this research job?",
          goal: "Ask the user for the research job schedule.",
          workflowState: { step: "collectSchedule", draft: nextDraft },
        });
      }
      return;
    }

    if (step === "collectMcpToolName") {
      const nextDraft = {
        ...draft,
        mcpToolName: value === "agent" ? undefined : trimmed,
      };
      setDraft(nextDraft);
      setStep("collectMcpPrompt");
      await assistantReply({
        userInput: trimmed,
        fallback: "What prompt should I send to the MCP run?",
        goal: "Ask the user for the MCP prompt.",
        workflowState: { step: "collectMcpPrompt", draft: nextDraft },
      });
      return;
    }

    if (step === "collectMcpPrompt") {
      const nextDraft = { ...draft, mcpPrompt: trimmed };
      setDraft(nextDraft);

      if (draft.oneTime) {
        setStep("confirm");
        appendMessage({
          id: `${Date.now()}-assistant-confirm-mcp`,
          role: "assistant",
          content: buildConfirmation(nextDraft),
          timestamp: new Date(),
          options: ["Run now", "Start over"],
        });
      } else {
        setStep("collectSchedule");
        await assistantReply({
          userInput: trimmed,
          fallback: "What schedule should I save for this MCP job?",
          goal: "Ask the user for the MCP job schedule.",
          workflowState: { step: "collectSchedule", draft: nextDraft },
        });
      }
      return;
    }

    if (step === "collectSchedule") {
      const nextDraft = { ...draft, schedule: trimmed };
      setDraft(nextDraft);
      setStep("confirm");
      appendMessage({
        id: `${Date.now()}-assistant-confirm-scheduled`,
        role: "assistant",
        content: buildConfirmation(nextDraft),
        timestamp: new Date(),
        options: ["Run now", "Start over"],
      });
      return;
    }

    if (step === "confirm") {
      if (value === "start over") {
        resetConversation();
        return;
      }

      if (value !== "run now") {
        await assistantReply({
          userInput: trimmed,
          fallback: "Press `Run now` to launch it, or `Start over` if you want to change anything.",
          goal: "Ask the user to confirm the launch or restart.",
          workflowState: { step, draft },
          options: ["Run now", "Start over"],
        });
        return;
      }

      if (draft.jobType === "sql" && !draft.mcpServer) {
        setStep("collectSqlMcpServer");
        await assistantReply({
          userInput: trimmed,
          fallback:
            sqlMcpServerLabels.length > 0
              ? "Pick a database source before I launch this SQL job."
              : "Type the SQL MCP server name before I launch (e.g. `sql-dab`).",
          goal: "Require the user to choose an approved SQL MCP data source before launch.",
          workflowState: { step: "collectSqlMcpServer", draft, sql_mcp_servers: sqlMcpServerLabels },
          options: sqlMcpServerLabels.length > 0 ? sqlMcpServerLabels : undefined,
        });
        return;
      }

      setIsLaunching(true);
      appendMessage({
        id: `${Date.now()}-assistant-launching`,
        role: "system",
        content: "Launching your job and creating the run record...",
        timestamp: new Date(),
      });

      try {
        const { resource, run } = await launchJobFromChat(draft);
        appendMessage({
          id: `${Date.now()}-assistant-done`,
          role: "assistant",
          content:
            `Your job is live.\n\n` +
            `Resource: ${resource.name}\n` +
            `Run ID: ${run.id}\n` +
            `Status: ${mapStatusLabel(run.status)}\n` +
            `MCP server: ${displayServerName(resource.connector)}\n\n` +
            `You can track it from the Jobs side panel and the Runs/Calendar panel on User Home.`,
          timestamp: new Date(),
          options: ["Start over"],
        });
      } catch (err) {
        appendMessage({
          id: `${Date.now()}-assistant-failed`,
          role: "assistant",
          content:
            `I couldn't start that run.\n\n${err instanceof Error ? err.message : "Unknown error"}\n\n` +
            `Check that the backend is running and that your bearer token is available.`,
          timestamp: new Date(),
          options: ["Start over"],
        });
      } finally {
        setIsLaunching(false);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <aside className="flex h-full w-full flex-shrink-0 flex-col overflow-hidden border-l border-gray-200 bg-white">
      <div className="flex flex-shrink-0 items-center justify-between border-b-2 border-gray-100 bg-gradient-to-r from-gray-50 to-white px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ed0923]/15">
            <MessageSquare className="h-5 w-5 text-[#ed0923]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold leading-tight text-gray-900">Chat Assistant</h3>
            <p className="text-xs leading-tight text-gray-500">Guided job launch</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={resetConversation}
            className="rounded-lg p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
            title="Start new chat"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
            title="Close panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="border-b border-gray-100 bg-gray-50 px-4 py-3 text-xs text-gray-600">
        <div className="flex items-center gap-2">
          <Play className="h-3.5 w-3.5 text-[#ed0923]" />
          <span>{currentPrompt}</span>
        </div>
        <div className="mt-2 flex items-center gap-4 text-[11px] text-gray-500">
          <span className="inline-flex items-center gap-1">
            <Clock3 className="h-3 w-3" />
            One-time or scheduled
          </span>
          <span className="inline-flex items-center gap-1">
            <Server className="h-3 w-3" />
            MCP-backed jobs
          </span>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm ${
                message.role === "user"
                  ? "bg-[#ed0923] text-white"
                  : message.role === "system"
                    ? "border border-amber-200 bg-amber-50 text-amber-900"
                    : "bg-gray-100 text-gray-900"
              }`}
            >
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
              {message.options && message.options.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {message.options.map((option) => (
                    <button
                      key={`${message.id}-${option}`}
                      onClick={() => void handleConversationTurn(option)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                        message.role === "user"
                          ? "border-white/20 bg-white/10 text-white"
                          : "border-gray-300 bg-white text-gray-700 hover:border-[#ed0923] hover:text-[#ed0923]"
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ))}

        {isLaunching ? (
          <div className="flex justify-start">
            <div className="inline-flex items-center gap-2 rounded-2xl bg-gray-100 px-4 py-3 text-sm text-gray-700">
              <Loader2 className="h-4 w-4 animate-spin" />
              Starting your run
            </div>
          </div>
        ) : null}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-200 p-4">
        {error ? <p className="mb-2 text-xs text-red-600">{error}</p> : null}
        <div className="flex gap-2">
          <textarea
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleConversationTurn(inputValue);
              }
            }}
            placeholder="Answer the current question..."
            className="min-h-[52px] flex-1 resize-none rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
          />
          <button
            onClick={() => void handleConversationTurn(inputValue)}
            disabled={!inputValue.trim() || isLaunching}
            className="flex h-[52px] w-[52px] items-center justify-center rounded-xl bg-[#ed0923] text-white transition hover:bg-[#d10820] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
