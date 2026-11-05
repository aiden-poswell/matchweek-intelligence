export function LoadingPanel() {
  return (
    <div className="status-panel" role="status" aria-live="polite">
      Loading historical fixture data…
    </div>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="status-panel status-panel--error" role="alert">
      <p>
        <strong>Unable to load historical fixture data.</strong>
      </p>
      <p>{message}</p>
      <p>
        No placeholder or illustrative data is shown in its place — if this fixture
        dataset cannot be loaded, nothing is displayed.
      </p>
    </div>
  );
}

export function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="status-panel" role="status">
      {message}
    </div>
  );
}
