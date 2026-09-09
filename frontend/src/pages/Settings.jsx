import React, { useEffect, useMemo, useState } from 'react';
import { Search, Loader2, Check, ExternalLink, Unplug } from 'lucide-react';
import Layout from '../components/Layout';
import { Sheet, Empty, Ruling, Stamp } from '../components/doc/Doc';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import api, { endpoints } from '../utils/api';
import { formatCurrency } from '../utils/formatters';
import { cn } from '../utils/cn';

/**
 * Standing instructions: who the broker is, what the engine is allowed to
 * trade and how large, and which model writes the theses.
 */

const Row = ({ label, hint, children }) => (
  <div className="py-3 border-b border-[var(--rule)] last:border-b-0">
    <div className="flex items-baseline justify-between gap-4 flex-wrap">
      <div className="min-w-0">
        <p className="field-label">{label}</p>
        {hint && <p className="doc-meta normal-case mt-1">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  </div>
);

const NumberField = ({ value, onChange, onCommit }) => (
  <input
    type="number"
    inputMode="numeric"
    value={value}
    onChange={(event) => onChange(event.target.value)}
    onBlur={onCommit}
    className="w-36 bg-transparent border-b border-[var(--rule-strong)] py-1 text-right figure-md text-sm focus:outline-none focus:border-[var(--stamp)]"
  />
);

/* -------------------------------------------------------------------------- */
/* Broker                                                                     */
/* -------------------------------------------------------------------------- */

const BROKER_TONE = {
  ACTIVE: 'success',
  NEEDS_LOGIN: 'warning',
  DEGRADED: 'destructive',
  UNCONFIGURED: 'secondary',
};

const BROKER_LABEL = { kite: 'Zerodha Kite', upstox: 'Upstox', angel_one: 'Angel One' };

const TextField = ({ id, label, ...props }) => (
  <div>
    <label htmlFor={id} className="field-label block mb-1">
      {label}
    </label>
    <input
      id={id}
      autoComplete="off"
      className="w-full bg-transparent border-b border-[var(--rule-strong)] py-1.5 text-sm focus:outline-none focus:border-[var(--stamp)]"
      {...props}
    />
  </div>
);

const BrokerSheet = () => {
  const [broker, setBroker] = useState('kite');
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  // Credential-save form (shown when UNCONFIGURED).
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [redirectUri, setRedirectUri] = useState('');

  // Redirect-flow connect (Kite / Upstox): paste the code/request_token.
  const [requestToken, setRequestToken] = useState('');

  // Credential-flow connect (Angel One): submitted fresh every time.
  const [clientCode, setClientCode] = useState('');
  const [password, setPassword] = useState('');
  const [totp, setTotp] = useState('');

  const refresh = (forBroker) =>
    api
      .get(endpoints.broker.status(forBroker))
      .then((res) => setState(res.data))
      .catch(() => setState({ state: 'UNCONFIGURED', connected: false, action: null }));

  useEffect(() => {
    setState(null);
    setNote(null);
    refresh(broker);
  }, [broker]);

  const needsSecret = broker !== 'angel_one';
  const needsRedirectUri = broker === 'upstox';

  const saveCredentials = async () => {
    if (!apiKey.trim() || (needsSecret && !apiSecret.trim())) return;
    setBusy(true);
    setNote(null);
    try {
      await api.post(endpoints.settings.brokerCredentials, {
        broker,
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim() || undefined,
        extra: needsRedirectUri ? redirectUri.trim() || undefined : undefined,
      });
      setApiKey('');
      setApiSecret('');
      setRedirectUri('');
      await refresh(broker);
    } catch (err) {
      setNote(err?.response?.data?.detail || 'Could not save the credentials');
    } finally {
      setBusy(false);
    }
  };

  const openLogin = async () => {
    setBusy(true);
    setNote(null);
    try {
      const res = await api.get(endpoints.broker.loginUrl(broker));
      window.open(res.data.url, '_blank', 'noopener');
      setNote(`Complete the ${BROKER_LABEL[broker]} login, then paste the code from the redirect URL.`);
    } catch (err) {
      setNote(err?.response?.data?.detail || 'Could not build the login URL');
    } finally {
      setBusy(false);
    }
  };

  const connectWithRequestToken = async () => {
    if (!requestToken.trim()) return;
    setBusy(true);
    setNote(null);
    try {
      await api.post(endpoints.broker.connect(broker), { request_token: requestToken.trim() });
      setRequestToken('');
      await refresh(broker);
    } catch (err) {
      setNote(err?.response?.data?.detail || `${BROKER_LABEL[broker]} rejected that code`);
    } finally {
      setBusy(false);
    }
  };

  const connectWithCredentials = async () => {
    if (!clientCode.trim() || !password.trim() || !totp.trim()) return;
    setBusy(true);
    setNote(null);
    try {
      await api.post(endpoints.broker.connect(broker), {
        client_code: clientCode.trim(), password, totp: totp.trim(),
      });
      setClientCode('');
      setPassword('');
      setTotp('');
      await refresh(broker);
    } catch (err) {
      setNote(err?.response?.data?.detail || `${BROKER_LABEL[broker]} rejected that login`);
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await api.post(endpoints.broker.disconnect(broker));
      await refresh(broker);
    } finally {
      setBusy(false);
    }
  };

  const brokerPicker = (
    <div className="flex gap-1">
      {Object.keys(BROKER_LABEL).map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => setBroker(key)}
          className={cn(
            'field-label px-2 py-1 border',
            key === broker
              ? 'border-[var(--stamp)] text-[var(--stamp)]'
              : 'border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-soft)]',
          )}
        >
          {BROKER_LABEL[key]}
        </button>
      ))}
    </div>
  );

  if (!state) {
    return (
      <Sheet title="Broker" actions={brokerPicker}>
        <Ruling rows={2} />
      </Sheet>
    );
  }

  return (
    <Sheet
      title="Broker"
      actions={
        <div className="flex items-center gap-3">
          {brokerPicker}
          <Badge variant={BROKER_TONE[state.state]}>{state.state.replace('_', ' ')}</Badge>
        </div>
      }
    >
      <p className="text-sm text-[var(--ink-soft)]">
        A connected {BROKER_LABEL[broker]} session supplies live tick data for intraday runs.
        Orders stay simulated — no real money moves, in either direction.
      </p>

      {state.state === 'UNCONFIGURED' ? (
        <div className="mt-4 space-y-3">
          <p className="doc-meta normal-case">
            {needsSecret
              ? `Paste the API key and secret from your ${BROKER_LABEL[broker]} app to configure this server.`
              : `Paste the API key from your ${BROKER_LABEL[broker]} app. Your account password and TOTP are entered fresh each time you connect — never stored.`}
          </p>
          <TextField id="broker-api-key" label="API key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          {needsSecret && (
            <TextField
              id="broker-api-secret" label="API secret" type="password"
              value={apiSecret} onChange={(e) => setApiSecret(e.target.value)}
            />
          )}
          {needsRedirectUri && (
            <TextField
              id="broker-redirect-uri" label="Redirect URI (registered with Upstox)"
              value={redirectUri} onChange={(e) => setRedirectUri(e.target.value)}
              placeholder="https://your-app.example.com/callback"
            />
          )}
          <Button
            variant="primary" size="sm" onClick={saveCredentials}
            disabled={busy || !apiKey.trim() || (needsSecret && !apiSecret.trim())}
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            Save
          </Button>
        </div>
      ) : state.connected ? (
        <div className="mt-4 flex items-center justify-between gap-4">
          <Stamp label="Connected" tone="gain" />
          <Button variant="secondary" size="sm" onClick={disconnect} disabled={busy}>
            <Unplug className="w-3.5 h-3.5" />
            Disconnect
          </Button>
        </div>
      ) : broker === 'angel_one' ? (
        <div className="mt-4 space-y-3">
          <TextField id="angel-client-code" label="Client code" value={clientCode} onChange={(e) => setClientCode(e.target.value)} />
          <TextField id="angel-password" label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <TextField
            id="angel-totp" label="TOTP (from your authenticator app)" inputMode="numeric"
            value={totp} onChange={(e) => setTotp(e.target.value)}
          />
          <Button
            variant="primary" size="sm" onClick={connectWithCredentials}
            disabled={busy || !clientCode.trim() || !password.trim() || !totp.trim()}
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            Connect
          </Button>
          <p className="doc-meta normal-case">Sessions end at midnight IST.</p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <Button variant="primary" size="sm" onClick={openLogin} disabled={busy}>
            <ExternalLink className="w-3.5 h-3.5" />
            Connect {BROKER_LABEL[broker]}
          </Button>

          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label htmlFor="request-token" className="field-label block mb-1">
                {broker === 'upstox' ? 'Code' : 'Request token'}
              </label>
              <input
                id="request-token"
                value={requestToken}
                onChange={(event) => setRequestToken(event.target.value)}
                placeholder="From the redirect URL after login"
                className="w-full bg-transparent border-b border-[var(--rule-strong)] py-1.5 text-sm focus:outline-none focus:border-[var(--stamp)]"
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={connectWithRequestToken}
              disabled={busy || !requestToken.trim()}
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              Submit
            </Button>
          </div>

          <p className="doc-meta normal-case">
            {broker === 'kite'
              ? 'The token is single-use and expires in minutes. Sessions end daily at 06:00 IST.'
              : 'The code is single-use and expires in minutes. Sessions end daily at 03:30 IST.'}
          </p>
        </div>
      )}

      {note && <p className="mt-3 text-sm text-[var(--ink-soft)]">{note}</p>}
    </Sheet>
  );
};

/* -------------------------------------------------------------------------- */
/* Mandate                                                                    */
/* -------------------------------------------------------------------------- */

const MandateSheet = () => {
  const [prefs, setPrefs] = useState(null);
  const [draft, setDraft] = useState({ account_size: '', max_exposure: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get(endpoints.settings.preferences)
      .then((res) => {
        setPrefs(res.data);
        setDraft({
          account_size: res.data.account_size,
          max_exposure: res.data.max_exposure,
        });
      })
      .catch(() => setPrefs(null));
  }, []);

  const save = async (patch) => {
    setSaving(true);
    try {
      const res = await api.put(endpoints.settings.preferences, patch);
      setPrefs(res.data);
    } finally {
      setSaving(false);
    }
  };

  if (!prefs) {
    return (
      <Sheet title="Mandate">
        <Ruling rows={3} />
      </Sheet>
    );
  }

  return (
    <Sheet
      title="Mandate"
      meta={saving ? 'Saving…' : undefined}
    >
      <Row
        label="Account size"
        hint="What position sizing risks a percentage of."
      >
        <NumberField
          value={draft.account_size}
          onChange={(value) => setDraft((d) => ({ ...d, account_size: value }))}
          onCommit={() => save({ account_size: Number(draft.account_size) })}
        />
      </Row>

      <Row label="Maximum exposure" hint="The engine will not open past this notional.">
        <NumberField
          value={draft.max_exposure}
          onChange={(value) => setDraft((d) => ({ ...d, max_exposure: value }))}
          onCommit={() => save({ max_exposure: Number(draft.max_exposure) })}
        />
      </Row>

      <Row
        label="Daily scan"
        hint="Runs after the close at 16:00 IST and files proposals for your decision."
      >
        <button
          type="button"
          role="switch"
          aria-checked={prefs.scan_enabled}
          onClick={() => save({ scan_enabled: !prefs.scan_enabled })}
          className={cn(
            'px-3 py-1 border font-[family-name:var(--font-narrow)] text-[0.6875rem] font-semibold uppercase tracking-[0.11em] transition-colors',
            prefs.scan_enabled
              ? 'bg-[var(--ink)] text-[var(--paper)] border-[var(--ink)]'
              : 'text-[var(--ink-soft)] border-[var(--rule-strong)]'
          )}
        >
          {prefs.scan_enabled ? 'On' : 'Off'}
        </button>
      </Row>

      <Row label="Scan universe" hint="Scrip the daily scan considers.">
        <span className="figure-md text-sm">{prefs.universe.length} scrip</span>
      </Row>

      <p className="pt-3 doc-meta normal-case">
        Sizing risks up to 1% of {formatCurrency(prefs.account_size)} per trade at full
        conviction, scaled down as conviction falls.
      </p>
    </Sheet>
  );
};

/* -------------------------------------------------------------------------- */
/* Model                                                                      */
/* -------------------------------------------------------------------------- */

const ModelSheet = () => {
  const [models, setModels] = useState([]);
  const [current, setCurrent] = useState('');
  const [selected, setSelected] = useState('');
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState(null);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.get(endpoints.settings.omnirouteModels),
      api.get(endpoints.settings.omnirouteModel),
    ])
      .then(([modelsRes, currentRes]) => {
        if (cancelled) return;
        setModels(modelsRes.data);
        setCurrent(currentRes.data.model);
        setSelected(currentRes.data.model);
      })
      .catch(() => {
        if (!cancelled) setLoadError('Could not reach the OmniRoute gateway.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    const list = term ? models.filter((m) => m.id.toLowerCase().includes(term)) : models;
    return list.slice(0, 40);
  }, [models, query]);

  const save = async () => {
    if (!selected.trim()) return;
    setSaving(true);
    setNote(null);
    try {
      await api.post(endpoints.settings.omnirouteModel, { model: selected });
      setCurrent(selected);
      setNote('Saved.');
    } catch (err) {
      setNote(
        err?.response?.status === 403
          ? 'The model applies to every account, so only an administrator can change it.'
          : 'Could not save the model.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet title="Analysis model" meta={`${models.length} available`}>
      {loadError ? (
        <Empty title="Gateway unreachable" detail={loadError} />
      ) : (
        <>
          <p className="text-sm text-[var(--ink-soft)]">
            Writes the thesis on each proposal and answers in chat. The trading engine itself
            never calls a model on the hot path.
          </p>

          <div className="mt-4">
            <label htmlFor="model-search" className="field-label block mb-1">
              In use
            </label>
            <div className="flex items-center gap-2 border-b border-[var(--rule-strong)] focus-within:border-[var(--stamp)]">
              <Search className="w-4 h-4 shrink-0 text-[var(--ink-faint)]" />
              <input
                id="model-search"
                value={open ? query : selected}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setOpen(true);
                }}
                onFocus={() => {
                  setQuery('');
                  setOpen(true);
                }}
                placeholder="Filter models"
                className="w-full bg-transparent border-0 py-2 text-sm figure-md focus:outline-none"
              />
            </div>

            {open && (
              <ul className="sheet mt-px max-h-64 overflow-y-auto">
                {filtered.length === 0 ? (
                  <li className="px-3 py-2.5 text-sm text-[var(--ink-soft)]">No match.</li>
                ) : (
                  filtered.map((model) => (
                    <li key={model.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelected(model.id);
                          setOpen(false);
                        }}
                        className="w-full text-left px-3 py-2 text-sm figure-md border-b border-[var(--rule)] last:border-b-0 hover:bg-[var(--stamp-soft)]"
                      >
                        {model.id}
                      </button>
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <span className="doc-meta normal-case truncate">
              {selected === current ? `Current: ${current}` : `Changing from ${current}`}
            </span>
            <Button
              variant="primary"
              size="sm"
              onClick={save}
              disabled={saving || selected === current}
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              Save
            </Button>
          </div>

          {note && <p className="mt-2 text-sm text-[var(--ink-soft)]">{note}</p>}
        </>
      )}
    </Sheet>
  );
};

const Settings = () => (
  <Layout>
    <div className="space-y-4 max-w-3xl">
      <BrokerSheet />
      <MandateSheet />
      <ModelSheet />
    </div>
  </Layout>
);

export default Settings;
