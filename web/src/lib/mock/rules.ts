import type { Rule } from "../types";

const CIRCULAR_2022 = "RBI/2022-23/108 (12 Aug 2022), recovery agents";
const RBC = "Responsible Business Conduct Directions";

// Drafted from RBI-domain search results and secondary summaries; RBI's site blocks automated reading,
// so no clause number is confirmed. See docs/rbi-references.md. Every entry stays marked until verified.
const REFS: Record<string, string> = {
  V1: `${CIRCULAR_2022}: no calls before 08:00 or after 19:00. Borrower-requested times: 2026 amendment RBI/2026-27/230. Clause: [to verify]`,
  V2: `${CIRCULAR_2022}, and ${RBC}: no intimidation or harassment, including abusive language. Clause: [to verify]`,
  V3: `${RBC}: no use of force; harsh recovery methods prohibited (para 100Z reported in the 2026 amendment). Clause: [to verify]`,
  V4: `${RBC}: no threats of unlawful action or misleading the borrower about the debt. Clause: [to verify]`,
  V5: `${RBC}: no public shaming, and no harassing relatives, friends or colleagues. Clause: [to verify]`,
  V6: `Fair Practices Code: borrower information stays confidential. Source not yet identified. Clause: [to verify]`,
  V7: `${RBC}: no misleading the borrower about the debt or the caller's authority. Clause: [to verify]`,
  V8: `Digital Lending Directions and the 2026 amendment: the borrower is told the recovery agency's details before contact. Clause: [to verify]`,
  V9: `${CIRCULAR_2022}: no persistent calling, intimidation or harassment. Clause: [to verify]`,
};

// Definitions follow plan.md Section 5.1.
export const RULES: Rule[] = [
  {
    code: "V1",
    name: "Call outside permitted hours",
    description:
      "The call started before 08:00 or after 19:00 IST and the borrower did not ask for that time. 08:00 and 19:00 themselves are allowed.",
    rbi_reference: REFS.V1,
    severity: "high",
    detection: "Call metadata",
    enabled: true,
  },
  {
    code: "V2",
    name: "Abusive or insulting language",
    description:
      "Profanity, slurs, name-calling or demeaning remarks directed at the borrower or their family. Quoting the borrower, firm but civil language and stating lawful consequences are not flagged.",
    rbi_reference: REFS.V2,
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V3",
    name: "Threat of physical harm or force",
    description:
      "A threat to harm, to send muscle, to seize property by force, or a menacing visit at home. A courteous notice that an executive may visit in permitted hours is not flagged.",
    rbi_reference: REFS.V3,
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V4",
    name: "False legal threat",
    description:
      "Claiming arrest, jail, FIR, warrant or police action as an imminent consequence of an ordinary default. Neutral mention of a legal notice or credit-bureau reporting is not flagged.",
    rbi_reference: REFS.V4,
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V5",
    name: "Public shaming or threat to inform others",
    description:
      "Threatening to tell the borrower's employer, colleagues, neighbours, relatives or society about the debt, or to publish their name or photo.",
    rbi_reference: REFS.V5,
    severity: "high",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V6",
    name: "Debt disclosed to a third party",
    description:
      "Revealing loan, amount or default details to someone who is not the borrower. Asking a third party to pass on a call-back request without disclosing the debt is not flagged.",
    rbi_reference: REFS.V6,
    severity: "high",
    detection: "LLM",
    enabled: true,
  },
  {
    code: "V7",
    name: "Impersonation or false authority",
    description:
      "Claiming to be police, court, advocate, government, RBI or CBI; falsely claiming a notice or case exists; materially false statements about the loan.",
    rbi_reference: REFS.V7,
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V8",
    name: "No self or lender identification",
    description:
      "In the first 60 seconds the agent does not state both their own name (or agent ID) and the lender's name.",
    rbi_reference: REFS.V8,
    severity: "medium",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V9",
    name: "Undue pressure or intimidation",
    description:
      "Ultimatums with menace, manufactured urgency, guilt-tripping through family, or repeated insistence after the borrower clearly states an inability to pay.",
    rbi_reference: REFS.V9,
    severity: "medium",
    detection: "Rules + LLM",
    enabled: true,
  },
];
