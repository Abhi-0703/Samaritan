# RBI references for the nine rules (draft, unverified)

Status: **no clause number here is confirmed.** RBI's website (rbi.org.in, rbidocs.rbi.org.in) serves its PDFs behind an image CAPTCHA, which automated tools must not bypass, so the primary text could not be read. The entries in `web/src/lib/mock/rules.ts` are drafted from RBI-domain search results (which confirm document titles and numbers) and from secondary summaries, and every one is marked `Clause: [to verify]`.

| Rule | Drafted reference | Evidence |
|---|---|---|
| V1 hours | RBI/2022-23/108 (12 Aug 2022): no calls before 08:00 or after 19:00; borrower-requested times from the 2026 amendment RBI/2026-27/230 | Document title and number seen on an RBI domain; the hours come from a search summary of it and from several blogs |
| V2 abuse | Same circular and the Responsible Business Conduct Directions: no intimidation or harassment | Search summary of the circular |
| V3 force | Responsible Business Conduct Directions: no use of force; "harsh recovery methods" (para 100Z reported) | Single secondary summary of the 2026 amendment |
| V4 false legal threat | Same directions: no threats of unlawful action or misleading the borrower | Secondary summary of the NBFC harsh-practices list |
| V5 shaming | Same directions: no public shaming, no harassing relatives, friends or colleagues | Secondary summary |
| V6 third-party disclosure | Fair Practices Code: confidentiality | **No source found** |
| V7 impersonation | Same directions: no misleading the borrower about the debt or the caller's authority | Secondary summary; authority part not found |
| V8 identification | Digital Lending Directions and the 2026 amendment: agency details given to the borrower before contact | Search summaries |
| V9 pressure | RBI/2022-23/108: no persistent calling, intimidation or harassment | Search summary |

## Conflicts found (resolve before claiming any clause)
- Hours: most sources say 08:00 to 19:00. One summary of the NBFC Master Direction's harsh-practices list says 09:00 to 18:00. plan.md uses 08:00 to 19:00 (Section 5.1), which matches the 2022 circular.
- The 2026 amendment (RBI/2026-27/230, effective 1 Jan 2027) and the "Responsible Business Conduct Directions, 2025" were seen only through summaries.
- Applicability differs: RBI/2022-23/108 covers commercial banks, RRBs, SFBs and AIFIs (not payment banks); NBFC rules sit in the 2023 Scale Based Regulation Master Direction (Chapter VII, para 45, Fair Practices Code), per one source.

## How to close this
Download these from rbi.org.in in a normal browser and save them under `docs/rbi-sources/` (public documents; not committed by default), or paste the relevant paragraphs: (1) RBI/2022-23/108, (2) RBI/2026-27/230, (3) the Responsible Business Conduct Directions, 2025, (4) the NBFC Scale Based Regulation Master Direction 2023, Chapter VII. Then each entry gets a real paragraph number, and the `[to verify]` marker is removed only after the user confirms.

## Sources used
- [RBI/2022-23/108, Outsourcing of Financial Services, responsibilities of regulated entities employing Recovery Agents](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT1085404663A577943BBB344A37057621C17.PDF)
- [RBI/2026-27/230](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT230A919C5A725694DD78C1C3640B455C4E9.PDF)
- [NBFC Scale Based Regulation Master Direction, 2023](https://rbidocs.rbi.org.in/rdocs/content/pdfs/106MDNBFCs19102023_ANN.pdf)
- [Master Circular, Fair Practices Code (RBI)](https://www.rbi.org.in/commonman/english/scripts/Notification.aspx?Id=867)
