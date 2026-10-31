import type { DetectedBy } from "../types";

export const BORROWER_NAMES = [
  "Anil Kumar", "Sandeep Jadhav", "Meena Kapoor", "Mahesh Salunkhe", "Ganesh Pawar", "Farhan Qureshi",
  "Mangesh Deshmukh", "Prakash Naik", "Dilip Kamble", "Divya Menon", "Harish Bhosale", "Suresh Gaikwad",
  "Lata Shinde", "Vaishali Jagtap", "Ashok Sawant", "Pradeep Mane", "Anjali Phadke", "Sunil Yadav",
  "Nitin Chavan", "Ajay Pandey", "Rajesh Gupta", "Kishor Waghmare", "Tanvi Desai", "Rohan Kulkarni",
  "Smita Ghosh", "Vivek Nair", "Deepa Iyer", "Arjun Reddy", "Neha Sharma", "Pankaj Thakur",
];

export const AMOUNTS = [3400, 4200, 5200, 5500, 7000, 7800, 9000, 12500, 16000];

export const HINGLISH_EXCUSES = [
  "Is mahine thoda tight chal raha hai. Agle hafte tak kar dunga.",
  "Salary aane mein company ne delay kar diya hai.",
  "Ghar mein shaadi thi, saara kharcha usi mein ho gaya.",
  "Dukaan mein abhi bikri kam hai, thoda time chahiye.",
  "Bachchon ki fees bharni padi, isliye EMI chhoot gayi.",
  "Maa ki tabiyat kharab thi, hospital mein paisa laga.",
];

export const HINGLISH_DAYS = ["Shukrawar", "Somvaar", "Shanivaar", "Guruwar", "Mangalwaar"];

export interface BankEntry {
  quote: string;
  lead: string;
  explanation: string;
  detected_by: DetectedBy;
}

// Violation phrases for generated calls. Each quote is a verbatim substring of the agent line (lead + quote).
export const HINGLISH_BANK: Record<string, BankEntry[]> = {
  V2: [
    { lead: "Aap jaise log hote hi aise hain,", quote: "tum jaise chor loan lekar bhaag jaate ho", explanation: "The agent calls the borrower a thief.", detected_by: "both" },
    { lead: "Mujhse baat mat karo,", quote: "bilkul nalayak aadmi ho tum", explanation: "The agent calls the borrower worthless.", detected_by: "both" },
    { lead: "Dekh,", quote: "tu bewakoof hai ya jaan bujh ke nahi bhar raha", explanation: "The agent insults the borrower's intelligence.", detected_by: "llm" },
  ],
  V3: [
    { lead: "Dhyan se sun,", quote: "ghar pe recovery wale bhej dunga, dekh lenge phir", explanation: "The agent threatens to send recovery men to the borrower's home.", detected_by: "both" },
    { lead: "Kal tak nahi aaya toh", quote: "hamare log ghar aake haath-pair tod denge", explanation: "The agent threatens physical harm.", detected_by: "both" },
    { lead: "Aap ghar par rahenge na kal?", quote: "Hum milne aayenge, aapke bachche bhi wahin honge", explanation: "A menacing reference to visiting the home with the children present.", detected_by: "llm" },
  ],
  V4: [
    { lead: "Aap samajh lijiye,", quote: "kal police aa jayegi aur jail bhej denge", explanation: "The agent claims police will arrive tomorrow and send the borrower to jail.", detected_by: "both" },
    { lead: "Ab baat badh gayi hai,", quote: "arrest warrant nikalwa raha hoon", explanation: "The agent claims an arrest warrant is being issued over an ordinary default.", detected_by: "both" },
    { lead: "Theek hai phir,", quote: "FIR darj karwa dunga aapke naam par", explanation: "The agent threatens an FIR over a missed EMI.", detected_by: "rules" },
  ],
  V5: [
    { lead: "Sunna hai toh sun lijiye,", quote: "office mein sabko bata denge ki aap defaulter hain", explanation: "The agent threatens to tell the borrower's colleagues about the debt.", detected_by: "both" },
    { lead: "Kal tak nahi aaya toh", quote: "padosiyon ko bata dunga ki aapne loan nahi bhara", explanation: "The agent threatens to tell the neighbours.", detected_by: "both" },
    { lead: "Theek hai,", quote: "aapke rishtedaaron ko call karke sab bata dunga", explanation: "The agent threatens to call the borrower's relatives about the debt.", detected_by: "llm" },
  ],
  V6: [
    { lead: "Aap unke bhai ho na? Toh suniye,", quote: "unhone loan liya hai aur teen mahine ki EMI nahi bhari", explanation: "The agent discloses the loan and the missed EMIs to a relative.", detected_by: "llm" },
    { lead: "Aap unki colleague hain? Dekhiye,", quote: "Mahesh ji ka loan overdue hai, 15000 rupaye baaki hain", explanation: "The agent discloses the amount overdue to a colleague.", detected_by: "llm" },
  ],
  V7: [
    { lead: "Seedhi baat bataun,", quote: "main court se bol raha hoon", explanation: "The agent falsely claims to be calling from the court.", detected_by: "both" },
    { lead: "Dhyan se suniye,", quote: "main high court ka advocate bol raha hoon", explanation: "The agent falsely claims to be an advocate.", detected_by: "both" },
    { lead: "Aapko batana zaroori hai,", quote: "aapke khilaaf case file ho chuka hai", explanation: "The agent falsely claims a case has already been filed.", detected_by: "llm" },
  ],
  V9: [
    { lead: "Mujhe kuch nahi sunna.", quote: "Abhi ke abhi payment karo, ye aakhri mauka hai", explanation: "A menacing ultimatum with manufactured urgency.", detected_by: "both" },
    { lead: "Dekhiye, aap bahaane bana rahe hain.", quote: "aaj hi paisa chahiye, kahin se bhi arrange karo", explanation: "Repeated insistence after the borrower states they cannot pay.", detected_by: "llm" },
    { lead: "Last baar bol raha hoon,", quote: "warna bahut bura hoga, ye last warning hai", explanation: "A menacing ultimatum.", detected_by: "rules" },
  ],
};

// Marathi violations in generated calls are limited to rules the test set covers in Marathi.
export const MARATHI_BANK: Record<string, BankEntry[]> = {
  V2: [{ lead: "ऐका,", quote: "तुम्ही नालायक आहात आणि कर्ज बुडवताय", explanation: "The agent calls the borrower worthless.", detected_by: "both" }],
  V4: [{ lead: "मी स्पष्ट सांगतो,", quote: "उद्या पोलीस तुमच्या दारात येतील", explanation: "The agent claims police will arrive tomorrow.", detected_by: "both" }],
  V5: [{ lead: "ठीक आहे मग,", quote: "आम्ही तुमच्या ऑफिसमध्ये सगळ्यांना सांगू", explanation: "The agent threatens to tell the borrower's office.", detected_by: "both" }],
  V9: [{ lead: "ऐका,", quote: "आत्ताच्या आत्ता पैसे भरा", explanation: "A menacing ultimatum with manufactured urgency.", detected_by: "llm" }],
};

export const BORROWER_REACTIONS_HINGLISH = [
  "Aap aisa kyun bol rahe hain? Main koshish kar raha hoon.",
  "Please, aisa mat kijiye. Main kuch kar leta hoon.",
  "Sir, mujhe thoda waqt dijiye, main bhaag nahi raha.",
];

export const BORROWER_REACTIONS_MARATHI = [
  "साहेब, असं का बोलताय? मी प्रयत्न करतोय.",
  "कृपया असं करू नका. मी काहीतरी करतो.",
];

export const MARATHI_OPENING = (agent: string, borrower: string) =>
  `नमस्कार, मी ${agent} बोलतोय सहयोग फायनान्स मधून. ${borrower} यांच्याशी बोलतोय का?`;

export const MARATHI_FILLER: { speaker: "agent" | "borrower"; text: string }[] = [
  { speaker: "borrower", text: "हो, बोला." },
  { speaker: "agent", text: "तुमच्या पर्सनल लोनचा हप्ता थकलेला आहे. कधी भरू शकाल?" },
  { speaker: "borrower", text: "या महिन्याच्या शेवटी करतो. पगार उशिरा होणार आहे." },
  { speaker: "agent", text: "कोणती तारीख नक्की सांगाल, म्हणजे मी नोंदवून ठेवतो." },
  { speaker: "borrower", text: "तीस तारखेला नक्की." },
];

export const MARATHI_TAIL: { speaker: "agent" | "borrower"; text: string }[] = [
  { speaker: "agent", text: "ठीक आहे, तीस तारीख नोंदवून ठेवतो. पेमेंटची लिंक एसएमएसने पाठवतो." },
  { speaker: "borrower", text: "ठीक आहे, धन्यवाद." },
  { speaker: "agent", text: "धन्यवाद. तुमचा दिवस चांगला जावो." },
];
