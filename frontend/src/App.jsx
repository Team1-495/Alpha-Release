import React, { useEffect, useState } from "react";
import * as api from "./api.js";

function scoreColor(s) {
  if (s >= 0.66) return "var(--score-high)";
  if (s >= 0.4) return "var(--score-mid)";
  return "var(--score-low)";
}

function LoginPanel({ session, onLogin, onError }) {
  const [username, setUsername] = useState("coordinator");
  const [password, setPassword] = useState("");

  if (session) {
    return (
      <div className="panel">
        <div className="panel-body">
          <h2>Signed in</h2>
          <div className="stat-row">
            <span>User</span>
            <span className="val">{session.username}</span>
          </div>
          <div className="stat-row">
            <span>Role</span>
            <span className="val">{session.role}</span>
          </div>
        </div>
      </div>
    );
  }

  const submit = async () => {
    try {
      const data = await api.login(username, password);
      onLogin({ username, role: data.role });
    } catch (e) {
      onError(e.message);
    }
  };

  return (
    <div className="panel">
      <div className="panel-body">
        <h2>Sign in to approve</h2>
        <div className="login-fields">
          <input
            aria-label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username"
          />
          <input
            aria-label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="Password"
          />
          <button onClick={submit}>Sign in</button>
        </div>
        <p className="hint">demo: coordinator / unite-demo</p>
      </div>
    </div>
  );
}

function Recommendation({ rec, isBest, canApprove, onApprove, onOverride }) {
  return (
    <div className="rec">
      <div className="sid">
        {rec.sponsor_id}
        {isBest && <span className="best">recommended</span>}
      </div>
      <div className="meter">
        <div className="track">
          <div
            className="fill"
            style={{ width: `${rec.score * 100}%`, background: scoreColor(rec.score) }}
          />
        </div>
        <span className="num">{rec.score.toFixed(2)}</span>
      </div>
      <div className="reasons">
        {rec.reasons.map((r, i) => (
          <span className="reason" key={i}>
            {r}
          </span>
        ))}
      </div>
      <div className="rec-actions">
        {isBest ? (
          <button
            className="approve"
            disabled={!canApprove}
            onClick={() => onApprove(rec.sponsor_id)}
          >
            Approve
          </button>
        ) : (
          <button
            className="override"
            disabled={!canApprove}
            onClick={() => onOverride(rec.sponsor_id)}
          >
            Override to this
          </button>
        )}
      </div>
    </div>
  );
}

function MatchRow({ result, decision, canApprove, onApprove, onOverride }) {
  const [open, setOpen] = useState(false);
  const status = decision
    ? decision.status
    : result.unmatched
      ? "unmatched"
      : "pending";

  return (
    <div className="row">
      <button className="row-summary" onClick={() => setOpen((v) => !v)}>
        <span className="id">{result.newcomer_id}</span>
        <span className="assigned">
          {result.unmatched ? (
            "no eligible sponsor with capacity"
          ) : (
            <>
              recommended sponsor <b>{result.assigned_sponsor_id}</b>
            </>
          )}
        </span>
        <span>
          {status !== "pending" && (
            <span className={`status-tag status-${status}`}>{status}</span>
          )}
        </span>
        <span className={`chev ${open ? "open" : ""}`}>›</span>
      </button>

      {open && (
        <div className="detail">
          {result.recommendations.length === 0 && (
            <p className="assigned">No eligible sponsors were found for this newcomer.</p>
          )}
          {result.recommendations.map((rec) => (
            <Recommendation
              key={rec.sponsor_id}
              rec={rec}
              isBest={rec.sponsor_id === result.assigned_sponsor_id}
              canApprove={canApprove}
              onApprove={(sid) => onApprove(result.newcomer_id, sid, false)}
              onOverride={(sid) => onOverride(result.newcomer_id, sid, true)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [newcomerCount, setNewcomerCount] = useState(null);
  const [results, setResults] = useState([]);
  const [decisions, setDecisions] = useState({}); // newcomer_id -> {sponsor_id,status}
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getNewcomers()
      .then((n) => setNewcomerCount(n.length))
      .catch((e) => setError(e.message));
  }, []);

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      const data = await api.runMatch(3);
      setResults(data);
      setDecisions({});
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const decide = async (newcomerId, sponsorId, override) => {
    setError("");
    try {
      const res = await api.approve(newcomerId, sponsorId, override);
      setDecisions((d) => ({ ...d, [newcomerId]: res }));
    } catch (e) {
      setError(e.message);
    }
  };

  const matched = results.filter((r) => !r.unmatched).length;
  const unmatched = results.length - matched;
  const approved = Object.keys(decisions).length;

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <h1>UNITE</h1>
          <span className="full">Unit Newcomer Integration &amp; Transition Engine</span>
        </div>
        <div className="session">
          {session ? (
            <>
              <span>{session.username}</span>
              <span className="role-chip">{session.role}</span>
            </>
          ) : (
            <span>not signed in</span>
          )}
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      <div className="layout">
        <aside className="rail">
          <div className="panel">
            <div className="panel-body">
              <h2>Cohort</h2>
              <button className="run-btn" onClick={run} disabled={running}>
                {running ? "Matching…" : "Run matching"}
              </button>
              <div style={{ marginTop: 14 }}>
                <div className="stat-row">
                  <span>Newcomers loaded</span>
                  <span className="val">{newcomerCount ?? "—"}</span>
                </div>
                <div className="stat-row">
                  <span>Recommended</span>
                  <span className="val">{matched}</span>
                </div>
                <div className="stat-row">
                  <span>Unmatched</span>
                  <span className="val">{unmatched}</span>
                </div>
                <div className="stat-row">
                  <span>Decisions recorded</span>
                  <span className="val">{approved}</span>
                </div>
              </div>
            </div>
          </div>

          <LoginPanel session={session} onLogin={setSession} onError={setError} />

          <div className="panel">
            <div className="panel-body">
              <p className="notice">
                Every profile here is synthetic. The matcher recommends; a coordinator
                always makes the final assignment.
              </p>
            </div>
          </div>
        </aside>

        <main className="matches">
          <div className="matches-head">
            <h2>Recommendations</h2>
            <span className="count">
              {results.length ? `${results.length} newcomers` : "run matching to begin"}
            </span>
          </div>

          {results.length === 0 ? (
            <div className="empty">
              No recommendations yet. Run matching to generate a ranked top-3 for each
              newcomer.
            </div>
          ) : (
            results.map((r) => (
              <MatchRow
                key={r.newcomer_id}
                result={r}
                decision={decisions[r.newcomer_id]}
                canApprove={Boolean(session)}
                onApprove={decide}
                onOverride={decide}
              />
            ))
          )}
        </main>
      </div>
    </>
  );
}
