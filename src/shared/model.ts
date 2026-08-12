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

export const PRACTICE_QUESTIONS = [
  {
    id: 'practice-commit-window',
    prompt: 'A Spring Boot consumer commits a PostgreSQL write, then crashes before acknowledging its SQS message. Walk through the retry and choose a protection.',
    hint: 'Name the failure window first. Which durable key can survive the retry and be checked atomically with the write?',
  },
  {
    id: 'practice-retention',
    prompt: 'Your idempotency ledger is growing quickly. Defend a retention policy without re-opening the duplicate window.',
    hint: 'Relate retention to the maximum redelivery and replay horizon, then name the remaining operational risk.',
  },
] as const

export const MOCK_PRIOR_TURNS = [
  {
    id: 'mock-turn-1',
    question: 'Place the idempotency boundary for a reservation command consumed from SQS.',
    answer: 'I would put the boundary at the consumer-to-domain command edge and carry the producer request ID into the same database transaction as the reservation write.',
  },
  {
    id: 'mock-turn-2',
    question: 'Now two consumers race with the same key. What makes your check safe?',
    answer: 'A unique key plus an atomic insert wins the race. A prior read is only an optimization; the constraint or compare-and-set decides the outcome.',
  },
] as const

export const MOCK_CURRENT_QUESTION = 'The idempotency store is unavailable for 30 seconds. What fails open or closed, and why?'
export const MOCK_FIXTURE_DRAFT = 'Fail closed for reservation creation, return a retryable failure, and keep the message unacknowledged. Failing open can create an irreversible duplicate. Bound retries, expose the dependency failure, and recover from the queue rather than claiming availability.'

export const FIXTURE_REPORT = {
  conclusion: 'The transcript defends a duplicate-safe write boundary and names the availability cost of failing closed.',
  nextAction: 'Practice the same decision when the duplicate key originates outside your trust boundary.',
  facts: [
    'The response keeps acknowledgement after the durable decision.',
    'The response treats the unique constraint or atomic insert as the race arbiter.',
  ],
  tradeoffs: [
    'Failing closed protects reservation integrity but makes the idempotency store part of the write-path availability budget.',
    'Queue redelivery preserves work but can amplify load unless retries are bounded and observable.',
  ],
  assumptions: ['The queue permits redelivery.', 'The duplicate key is stable for the replay horizon.', 'The database operation is atomic.'],
} as const

export const SIMULATION_LIMITATION = 'Deterministic browser fixture only — no Java process, network request, AWS service, or production environment is used.'
