export type AgentId = 'A' | 'B' | 'C';

export interface ReasoningStep {
  id: number;
  text: string;
  isShared?: boolean; // Highlight if shared across agents
}

export interface AgentData {
  id: AgentId;
  name: string;
  finalAnswer: string;
  reasoning: ReasoningStep[];
  assumptions: string[];
}

export interface Scenario {
  id: 'fragile' | 'robust';
  label: string;
  trustLevel: 'Fragile' | 'Uncertain' | 'Robust';
  trustDescription: string;
  agents: AgentData[];
}

const COMMON_QUESTION = "How many piano tuners are there in Chicago?";

// SCENARIO 1: FRAGILE (Groupthink / Mode Collapse)
// All agents use the exact same Fermi approximation variables.
const FRAGILE_REASONING: ReasoningStep[] = [
  { id: 1, text: "Population of Chicago is approx 2.7 million.", isShared: true },
  { id: 2, text: "Assume 2 people per household -> 1.35 million households.", isShared: true },
  { id: 3, text: "Assume 1 in 20 households has a piano -> 67,500 pianos.", isShared: true },
  { id: 4, text: " pianos tuned once per year -> 67,500 tunings/year.", isShared: true },
  { id: 5, text: "Tuner does 2 tunings/day * 5 days * 50 weeks = 500 tunings/year/tuner.", isShared: true },
  { id: 6, text: "Total tuners = 67,500 / 500 = 135 tuners.", isShared: true },
];

export const FRAGILE_SCENARIO: Scenario = {
  id: 'fragile',
  label: 'Consensus (Low Diversity)',
  trustLevel: 'Fragile',
  trustDescription: "High agreement, but identical reasoning paths suggest model collapse or shared error modes.",
  agents: [
    {
      id: 'A',
      name: 'Agent Alpha',
      finalAnswer: "Approx. 135 Tuners",
      reasoning: FRAGILE_REASONING,
      assumptions: ["Chicago pop = 2.7M", "1/20 piano ownership rate"],
    },
    {
      id: 'B',
      name: 'Agent Beta',
      finalAnswer: "Approx. 135 Tuners",
      reasoning: FRAGILE_REASONING,
      assumptions: ["Chicago pop = 2.7M", "1/20 piano ownership rate"],
    },
    {
      id: 'C',
      name: 'Agent Gamma',
      finalAnswer: "About 135 Tuners",
      reasoning: FRAGILE_REASONING,
      assumptions: ["Chicago pop = 2.7M", "1/20 piano ownership rate"],
    },
  ],
};

// SCENARIO 2: ROBUST (Diversity of Thought)
// Agents use different methods (Fermi, Employment Data, Business Listings) but converge.
export const ROBUST_SCENARIO: Scenario = {
  id: 'robust',
  label: 'Consensus (High Diversity)',
  trustLevel: 'Robust',
  trustDescription: "Strong consensus reached via independent reasoning paths (Fermi, Market Data, Historical).",
  agents: [
    {
      id: 'A',
      name: 'Agent Alpha',
      finalAnswer: "~130-140 Tuners",
      reasoning: [
        { id: 1, text: "Method: Fermi Estimation", isShared: false },
        { id: 2, text: "Chicago Population ~2.7M.", isShared: false },
        { id: 3, text: "Est. 135 tuners based on standard calculation.", isShared: false },
      ],
      assumptions: ["Standard consumption rates"],
    },
    {
      id: 'B',
      name: 'Agent Beta',
      finalAnswer: "~130 Tuners",
      reasoning: [
        { id: 1, text: "Method: Labor Market Analysis", isShared: false },
        { id: 2, text: "BLS data for 'Musical Instrument Repairers' in IL.", isShared: false },
        { id: 3, text: "Chicago metro area accounts for 70% of IL data.", isShared: false },
        { id: 4, text: "Adjusting for self-employed contractors.", isShared: false },
      ],
      assumptions: ["Official employment records are accurate"],
    },
    {
      id: 'C',
      name: 'Agent Gamma',
      finalAnswer: "~140 Tuners",
      reasoning: [
        { id: 1, text: "Method: Business Listing Proxy", isShared: false },
        { id: 2, text: "Scraping local business directories (Yelp, Google Maps).", isShared: false },
        { id: 3, text: "Found 85 registered businesses.", isShared: false },
        { id: 4, text: "Applying 1.6x multiplier for independent/unlisted operators.", isShared: false },
      ],
      assumptions: ["Digital presence correlation"],
    },
  ],
};
