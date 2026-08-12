export type Depth = 'Essential' | 'Implementation' | 'Production' | 'Interview'

export const CURRENT_LESSON_ID = 'idempotency-retry'

export const STARTER_CODE = `public Reservation reserve(String requestId, Supplier<Reservation> create) {
  var existing = ledger.find(requestId);
  if (existing.isPresent()) return existing.get();

  var reservation = create.get();
  ledger.save(requestId, reservation);
  return reservation;
}`

export const REFERENCE_CODE = `public Reservation reserve(String requestId, Supplier<Reservation> create) {
  return ledger.find(requestId).orElseGet(() -> {
    var candidate = create.get();
    return ledger.putIfAbsent(requestId, candidate).orElse(candidate);
  });
}`

export const SIMULATION_LIMITATION = 'Deterministic browser fixture only — no Java process, network request, AWS service, or production environment is used.'
