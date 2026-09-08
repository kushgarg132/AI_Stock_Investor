import React from 'react';
import { Sheet, Empty } from './doc/Doc';
import { Button } from './common/Button';

/**
 * A crash in one page (a data shape the frontend didn't expect, a bad API
 * response) currently white-screens the whole app -- there was no error
 * boundary anywhere in the tree. This catches at the page level so one
 * broken section degrades to a message instead of a blank sheet.
 */
class ErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Uncaught error in page tree:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <Sheet title="Something tore">
          <Empty
            title="This section could not be rendered"
            detail="The statement hit an unexpected error. Reloading the page usually clears it."
            action={
              <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
                Reload
              </Button>
            }
          />
        </Sheet>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
