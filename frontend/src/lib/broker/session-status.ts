/**
 * Broker page: an unknown session is not a disconnected session.
 *
 * 17 Nov 2026: with the trading terminal slow, the session request was still
 * loading / had failed, and the page showed the Connect form as if the
 * account were gone. The Connect form appears only when the backend says
 * there is no connected account, or the user chose "Change account".
 */
export type BrokerSessionQueryState = {
  hasData: boolean;
  isLoading: boolean;
  isError: boolean;
  changingAccount: boolean;
};

export function isBrokerSessionUnknown(q: BrokerSessionQueryState): boolean {
  if (q.changingAccount) return false;
  if (q.hasData) return false;
  return q.isLoading || q.isError;
}
