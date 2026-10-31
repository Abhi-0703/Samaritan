import type { Rule } from "../types";

const ref = (topic: string) =>
  `RBI Responsible Business Conduct Directions, recovery conduct: ${topic}. Clause: [to verify]`;

// Definitions follow plan.md Section 5.1.
export const RULES: Rule[] = [
  {
    code: "V1",
    name: "Call outside permitted hours",
    description:
      "The call started before 08:00 or after 19:00 IST and the borrower did not ask for that time. 08:00 and 19:00 themselves are allowed.",
    rbi_reference: ref("calls only between 08:00 and 19:00 unless the borrower requests otherwise"),
    severity: "high",
    detection: "Call metadata",
    enabled: true,
  },
  {
    code: "V2",
    name: "Abusive or insulting language",
    description:
      "Profanity, slurs, name-calling or demeaning remarks directed at the borrower or their family. Quoting the borrower, firm but civil language and stating lawful consequences are not flagged.",
    rbi_reference: ref("prohibition on harassment and abusive language"),
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V3",
    name: "Threat of physical harm or force",
    description:
      "A threat to harm, to send muscle, to seize property by force, or a menacing visit at home. A courteous notice that an executive may visit in permitted hours is not flagged.",
    rbi_reference: ref("prohibition on intimidation and use of force"),
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V4",
    name: "False legal threat",
    description:
      "Claiming arrest, jail, FIR, warrant or police action as an imminent consequence of an ordinary default. Neutral mention of a legal notice or credit-bureau reporting is not flagged.",
    rbi_reference: ref("prohibition on threats of legal action not backed by due process"),
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V5",
    name: "Public shaming or threat to inform others",
    description:
      "Threatening to tell the borrower's employer, colleagues, neighbours, relatives or society about the debt, or to publish their name or photo.",
    rbi_reference: ref("prohibition on public shaming and informing third parties"),
    severity: "high",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V6",
    name: "Debt disclosed to a third party",
    description:
      "Revealing loan, amount or default details to someone who is not the borrower. Asking a third party to pass on a call-back request without disclosing the debt is not flagged.",
    rbi_reference: ref("confidentiality of borrower information"),
    severity: "high",
    detection: "LLM",
    enabled: true,
  },
  {
    code: "V7",
    name: "Impersonation or false authority",
    description:
      "Claiming to be police, court, advocate, government, RBI or CBI; falsely claiming a notice or case exists; materially false statements about the loan.",
    rbi_reference: ref("prohibition on misrepresentation of identity or authority"),
    severity: "critical",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V8",
    name: "No self or lender identification",
    description:
      "In the first 60 seconds the agent does not state both their own name (or agent ID) and the lender's name.",
    rbi_reference: ref("recovery agents must identify themselves and the lender"),
    severity: "medium",
    detection: "Rules + LLM",
    enabled: true,
  },
  {
    code: "V9",
    name: "Undue pressure or intimidation",
    description:
      "Ultimatums with menace, manufactured urgency, guilt-tripping through family, or repeated insistence after the borrower clearly states an inability to pay.",
    rbi_reference: ref("prohibition on harassment and intimidation"),
    severity: "medium",
    detection: "Rules + LLM",
    enabled: true,
  },
];
