import type { Agent, Experiment } from "./types";

const COLORS = {
  group1: "#16877b",
  group1Pale: "#e5f4f0",
  group2: "#6562c8",
  group2Pale: "#eeedfb",
  ink: "#263449",
  muted: "#7b8798",
  line: "#e6eaf0",
};

function cumulativePayoff(run: Experiment, agentId: string, round: number) {
  return run.matches.reduce((total, match) => {
    if (match.round > round) return total;
    if (match.a === agentId) return total + match.payoff_a;
    if (match.b === agentId) return total + match.payoff_b;
    return total;
  }, 0);
}

interface GraphProps {
  run: Experiment;
  round: number;
  onSelectAgent: (id: string) => void;
  selectedAgent?: string;
}

export function InteractionGraph({
  run,
  round,
  onSelectAgent,
  selectedAgent,
}: GraphProps) {
  const settled = run.matches.filter((match) => match.round === round);
  const isPending = settled.length === 0 && run.pending?.round === round;
  const pendingPairs = isPending ? (run.pending?.pairs ?? []) : [];
  const count = run.agents.length;
  const radius = count > 16 ? 17 : count > 8 ? 23 : 28;
  const coordinates = new Map(
    run.agents.map((agent, index) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * index) / Math.max(count, 1);
      return [
        agent.id,
        { x: 300 + 215 * Math.cos(angle), y: 166 + 110 * Math.sin(angle) },
      ];
    }),
  );
  const paired = new Set(settled.flatMap((match) => [match.a, match.b]));
  const pendingByes = new Set(isPending ? (run.pending?.byes ?? []) : []);
  const hasPairing = settled.length > 0 || pendingPairs.length > 0;

  const renderEdge = (a: string, b: string, pending: boolean, key: string) => {
    const start = coordinates.get(a);
    const end = coordinates.get(b);
    if (!start || !end) return null;
    return (
      <line
        key={key}
        x1={start.x}
        y1={start.y}
        x2={end.x}
        y2={end.y}
        stroke={pending ? "#aab5c5" : "#c3cdd9"}
        strokeWidth={pending ? 1.5 : 2}
        strokeDasharray={pending ? "5 5" : undefined}
      />
    );
  };

  const renderAction = (
    agentId: string,
    opponentId: string,
    action: string,
    payoff: number,
  ) => {
    const start = coordinates.get(agentId);
    const end = coordinates.get(opponentId);
    if (!start || !end) return null;
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    const fraction = Math.min(0.31, (radius + 34) / Math.max(length, 1));
    const x = start.x + (end.x - start.x) * fraction;
    const y = start.y + (end.y - start.y) * fraction;
    const cooperation = action === "C";
    return (
      <g key={agentId} aria-hidden="true">
        <rect
          x={x - 24}
          y={y - 12}
          width="48"
          height="24"
          rx="8"
          fill={cooperation ? "#e7f5ee" : "#fff1e7"}
          stroke={cooperation ? "#cce9db" : "#f3ddca"}
        />
        <text
          x={x}
          y={y + 4}
          textAnchor="middle"
          fontSize="11"
          fontWeight="650"
          fill={cooperation ? "#277456" : "#a66a37"}
        >
          {action} · +{payoff}
        </text>
      </g>
    );
  };

  return (
    <div className="interaction-visualization">
      <svg
        viewBox="0 0 600 360"
        role="group"
        aria-label={`Agent interactions for round ${round}. Select an agent to inspect its records.`}
        style={{
          display: "block",
          width: "100%",
          height: "auto",
          fontFamily: "inherit",
        }}
      >
        <ellipse
          cx="300"
          cy="166"
          rx="215"
          ry="110"
          fill="none"
          stroke="#edf0f5"
          strokeDasharray="3 7"
        />
        {settled.map((match) =>
          renderEdge(match.a, match.b, false, `${match.a}-${match.b}`),
        )}
        {pendingPairs.map(([a, b], index) =>
          renderEdge(a, b, true, `pending-${index}`),
        )}
        {!hasPairing && (
          <g aria-hidden="true">
            <text
              x="300"
              y="159"
              textAnchor="middle"
              fill={COLORS.muted}
              fontSize="13"
              fontWeight="550"
            >
              No pairings yet
            </text>
            <text
              x="300"
              y="180"
              textAnchor="middle"
              fill="#99a3b2"
              fontSize="11"
            >
              Start the experiment to begin
            </text>
          </g>
        )}
        {isPending && hasPairing && (
          <g aria-hidden="true">
            <rect
              x="262"
              y="151"
              width="76"
              height="28"
              rx="14"
              fill="#f5f7fb"
              stroke="#e2e7ee"
            />
            <text
              x="300"
              y="169"
              textAnchor="middle"
              fill={COLORS.muted}
              fontSize="11"
              fontWeight="600"
            >
              Pending
            </text>
          </g>
        )}
        {settled.flatMap((match) => [
          renderAction(match.a, match.b, match.action_a, match.payoff_a),
          renderAction(match.b, match.a, match.action_b, match.payoff_b),
        ])}
        {run.agents.map((agent, index) => {
          const point = coordinates.get(agent.id)!;
          const isGroup1 = agent.group === 1;
          const selected = selectedAgent === agent.id;
          const isBye =
            pendingByes.has(agent.id) ||
            (round > 0 &&
              round <= run.round &&
              settled.length > 0 &&
              !paired.has(agent.id));
          const payoff = cumulativePayoff(run, agent.id, round);
          const match = settled.find(
            (entry) => entry.a === agent.id || entry.b === agent.id,
          );
          const action = match
            ? match.a === agent.id
              ? match.action_a
              : match.action_b
            : null;
          const accessibleLabel = `${agent.id}, Group ${agent.group}, cumulative payoff ${payoff}${isBye ? ", bye this round" : action ? `, action ${action === "C" ? "cooperate" : "defect"}` : ", no revealed action"}. Inspect agent.`;
          return (
            <g
              key={agent.id}
              className="graph-agent"
              role="button"
              tabIndex={0}
              aria-label={accessibleLabel}
              aria-pressed={selected}
              onClick={() => onSelectAgent(agent.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectAgent(agent.id);
                }
              }}
              style={{ cursor: "pointer", outlineOffset: 5 }}
            >
              <title>{accessibleLabel}</title>
              {selected && (
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={radius + 6}
                  fill="none"
                  stroke={isGroup1 ? COLORS.group1 : COLORS.group2}
                  strokeWidth="1.5"
                  opacity="0.45"
                />
              )}
              <circle
                cx={point.x}
                cy={point.y}
                r={radius}
                fill={isGroup1 ? COLORS.group1Pale : COLORS.group2Pale}
                stroke={isGroup1 ? COLORS.group1 : COLORS.group2}
                strokeWidth={selected ? 2 : 1.2}
              />
              <text
                x={point.x}
                y={point.y + 5}
                textAnchor="middle"
                fontSize={radius < 20 ? "11" : "14"}
                fontWeight="650"
                fill={isGroup1 ? COLORS.group1 : COLORS.group2}
                aria-hidden="true"
              >
                {String(index + 1).padStart(2, "0")}
              </text>
              <text
                x={point.x}
                y={point.y + radius + 19}
                textAnchor="middle"
                fontSize={count > 12 ? "9" : "11"}
                fill={COLORS.ink}
                fontWeight="600"
                aria-hidden="true"
              >
                {agent.id}
              </text>
              <text
                x={point.x}
                y={point.y + radius + 34}
                textAnchor="middle"
                fontSize="10"
                fill={COLORS.muted}
                aria-hidden="true"
              >
                {isBye ? "Bye · " : ""}
                {payoff} pts
              </text>
            </g>
          );
        })}
      </svg>
      <div
        className="graph-legend"
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "18px",
          fontSize: "11px",
          color: COLORS.muted,
        }}
      >
        <span>
          <span style={{ color: COLORS.group1 }}>●</span> Group 1
        </span>
        <span>
          <span style={{ color: COLORS.group2 }}>●</span> Group 2
        </span>
        <span>C = Cooperate · D = Defect</span>
      </div>
    </div>
  );
}

interface ChartProps {
  run: Experiment;
  round: number;
}

export function PayoffChart({ run, round }: ChartProps) {
  const maximumRound = Math.max(0, Math.min(round, run.round));
  const matches = run.matches.filter((match) => match.round <= maximumRound);
  if (matches.length === 0) {
    return (
      <div
        className="chart-empty"
        style={{
          minHeight: 175,
          display: "grid",
          placeItems: "center",
          color: COLORS.muted,
          fontSize: 13,
        }}
      >
        Complete a round to see cumulative payoff.
      </div>
    );
  }
  const agents = new Map<string, Agent>(
    run.agents.map((agent) => [agent.id, agent]),
  );
  const totals: [number, number][] = Array.from(
    { length: maximumRound + 1 },
    () => [0, 0],
  );
  for (const match of matches) {
    const aGroup = agents.get(match.a)?.group;
    const bGroup = agents.get(match.b)?.group;
    if (aGroup) totals[match.round][aGroup - 1] += match.payoff_a;
    if (bGroup) totals[match.round][bGroup - 1] += match.payoff_b;
  }
  for (let index = 1; index < totals.length; index += 1) {
    totals[index][0] += totals[index - 1][0];
    totals[index][1] += totals[index - 1][1];
  }
  const last = totals[totals.length - 1];
  const ceiling = Math.max(5, Math.ceil(Math.max(...totals.flat()) / 5) * 5);
  const left = 42;
  const right = 576;
  const top = 17;
  const bottom = 149;
  const x = (value: number) =>
    left + (value / Math.max(maximumRound, 1)) * (right - left);
  const y = (value: number) => bottom - (value / ceiling) * (bottom - top);
  const points = (group: 0 | 1) =>
    totals.map((values, index) => `${x(index)},${y(values[group])}`).join(" ");
  const xTicks = Array.from(
    new Set([0, Math.ceil(maximumRound / 2), maximumRound]),
  );

  return (
    <div className="payoff-visualization">
      <svg
        viewBox="0 0 600 186"
        role="img"
        aria-label={`Cumulative group payoff through round ${maximumRound}. Group 1: ${last[0]} points. Group 2: ${last[1]} points.`}
        style={{
          display: "block",
          width: "100%",
          height: "auto",
          fontFamily: "inherit",
        }}
      >
        <title>Cumulative payoff by group</title>
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const value = ceiling * fraction;
          return (
            <g key={fraction}>
              <line
                x1={left}
                x2={right}
                y1={y(value)}
                y2={y(value)}
                stroke={COLORS.line}
                strokeDasharray={fraction ? "3 4" : undefined}
              />
              <text
                x={left - 10}
                y={y(value) + 4}
                textAnchor="end"
                fill={COLORS.muted}
                fontSize="10"
              >
                {Number(value.toFixed(1))}
              </text>
            </g>
          );
        })}
        {xTicks.map((value) => (
          <text
            key={value}
            x={x(value)}
            y={bottom + 19}
            textAnchor="middle"
            fill={COLORS.muted}
            fontSize="10"
          >
            {value}
          </text>
        ))}
        <text
          x={right}
          y="183"
          textAnchor="end"
          fill={COLORS.muted}
          fontSize="9"
        >
          Round
        </text>
        <polyline
          points={points(0)}
          fill="none"
          stroke={COLORS.group1}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <polyline
          points={points(1)}
          fill="none"
          stroke={COLORS.group2}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={x(maximumRound)}
          cy={y(last[0])}
          r="3.5"
          fill={COLORS.group1}
          stroke="white"
          strokeWidth="1.5"
        />
        <circle
          cx={x(maximumRound)}
          cy={y(last[1])}
          r="3.5"
          fill={COLORS.group2}
          stroke="white"
          strokeWidth="1.5"
        />
      </svg>
      <div
        className="payoff-legend"
        style={{
          display: "flex",
          justifyContent: "center",
          flexWrap: "wrap",
          gap: 22,
          fontSize: 11,
          color: COLORS.muted,
        }}
      >
        <span>
          <span style={{ color: COLORS.group1 }}>━</span> Group 1{" "}
          <strong style={{ color: COLORS.ink }}>{last[0]}</strong>
        </span>
        <span>
          <span style={{ color: COLORS.group2 }}>━</span> Group 2{" "}
          <strong style={{ color: COLORS.ink }}>{last[1]}</strong>
        </span>
        <span>Group totals, not per-agent averages</span>
      </div>
    </div>
  );
}
