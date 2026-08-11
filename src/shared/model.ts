export type KnowledgeState = 'likely known' | 'partial' | 'unverified' | 'new'
export type Depth = 'Essential' | 'Implementation' | 'Production' | 'Interview'

export interface Lesson {
  id: string
  title: string
  duration: string
  capability: 'understand' | 'choose' | 'implement' | 'diagnose' | 'defend'
  state: KnowledgeState
  recommendedDepth: Depth
  kind: 'read' | 'lab' | 'review'
}

export interface CourseModule {
  id: string
  title: string
  duration: string
  lessons: readonly Lesson[]
}

export interface CourseFixture {
  id: string
  title: string
  shortTitle: string
  target: string
  subject: string
  goal: string
  progressLabel: string
  modules: readonly CourseModule[]
}

export const COURSE: CourseFixture = {
  id: 'resilient-order-fulfillment',
  title: 'Resilient order fulfillment with Spring Boot and SQS',
  shortTitle: 'Resilient order fulfillment',
  target: 'Senior backend engineer',
  subject: 'Java / Spring Boot · AWS',
  goal: 'Design, implement, diagnose, and defend duplicate-safe message handling.',
  progressLabel: '4 of 11 lessons have qualified evidence',
  modules: [
    {
      id: 'failure-boundaries',
      title: 'Frame the failure boundary',
      duration: '42 min',
      lessons: [
        { id: 'delivery-contract', title: 'Model the delivery contract before choosing a pattern', duration: '10 min', capability: 'understand', state: 'likely known', recommendedDepth: 'Essential', kind: 'read' },
        { id: 'commit-window', title: 'Trace the commit-and-acknowledgement failure window', duration: '14 min', capability: 'diagnose', state: 'partial', recommendedDepth: 'Implementation', kind: 'lab' },
      ],
    },
    {
      id: 'duplicate-control',
      title: 'Control duplicates and ordering',
      duration: '1 hr 36 min',
      lessons: [
        { id: 'idempotency-retry', title: 'Implement an idempotency boundary under concurrent retries', duration: '24 min', capability: 'implement', state: 'partial', recommendedDepth: 'Implementation', kind: 'lab' },
        { id: 'atomic-write', title: 'Keep the business write and duplicate marker atomic', duration: '18 min', capability: 'choose', state: 'unverified', recommendedDepth: 'Implementation', kind: 'read' },
        { id: 'delayed-duplicates', title: 'Design for delayed, duplicated, and out-of-order deliveries without hiding the trade-offs', duration: '28 min', capability: 'defend', state: 'new', recommendedDepth: 'Production', kind: 'lab' },
        { id: 'visibility-timeout', title: 'Tune visibility timeout and bounded retry budgets', duration: '16 min', capability: 'choose', state: 'partial', recommendedDepth: 'Production', kind: 'read' },
        { id: 'dead-letter', title: 'Diagnose poison messages and dead-letter recovery', duration: '10 min', capability: 'diagnose', state: 'unverified', recommendedDepth: 'Production', kind: 'review' },
      ],
    },
    {
      id: 'operational-proof',
      title: 'Collect operational evidence',
      duration: '54 min',
      lessons: [
        { id: 'observability', title: 'Instrument retry, duplicate, and latency signals', duration: '16 min', capability: 'implement', state: 'unverified', recommendedDepth: 'Production', kind: 'lab' },
        { id: 'failure-injection', title: 'Use bounded failure injection to inspect recovery', duration: '22 min', capability: 'diagnose', state: 'new', recommendedDepth: 'Production', kind: 'lab' },
      ],
    },
    {
      id: 'defend-system',
      title: 'Defend the system',
      duration: '38 min',
      lessons: [
        { id: 'tradeoff-review', title: 'Defend the consistency and availability choices', duration: '20 min', capability: 'defend', state: 'unverified', recommendedDepth: 'Interview', kind: 'review' },
        { id: 'transfer-check', title: 'Transfer the pattern to a new failure scenario', duration: '18 min', capability: 'defend', state: 'new', recommendedDepth: 'Interview', kind: 'review' },
      ],
    },
  ],
}

export const CURRENT_LESSON_ID = 'idempotency-retry'
export const CURRENT_MODULE_INDEX = 1
export const CURRENT_LESSON_INDEX = 2

export const ALL_LESSONS = COURSE.modules.flatMap((module) => module.lessons)
export const CURRENT_LESSON = ALL_LESSONS.find((lesson) => lesson.id === CURRENT_LESSON_ID)!

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

export const TOPIC_BRIEF = {
  problem: 'Two consumers receive the same reservation request while neither can see a committed duplicate marker.',
  task: 'Close the check-then-write race without claiming that this prototype executes Java or proves production behavior.',
  evidence: 'Submit a revision that makes the duplicate boundary explicit and explain the atomicity assumption.',
  source: 'AWS SQS Developer Guide · Amazon SQS at-least-once delivery',
  sourceUrl: 'https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html',
} as const

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
