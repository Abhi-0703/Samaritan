import type { DetectedBy, Language, ReviewerStatus } from "../types";

export interface SegSpec {
  speaker: "agent" | "borrower";
  text: string;
}

export interface VioSpec {
  rule: string;
  seg: number | null; // segment index; null for V1 (metadata) and V8 (first 60 seconds)
  quote: string | null;
  explanation: string;
  confidence: number;
  detected_by: DetectedBy;
  reviewer?: ReviewerStatus;
}

export interface FeaturedCall {
  test_key: string;
  agent: string;
  language: Language;
  ist_time: string; // HH:MM
  days_ago: number;
  duration_s: 105 | 140 | 180; // matches a generated placeholder audio file
  loan_ref: string;
  segments: SegSpec[];
  violations: VioSpec[];
}

const A = (text: string): SegSpec => ({ speaker: "agent", text });
const B = (text: string): SegSpec => ({ speaker: "borrower", text });

// Adapted from the Phase 0 scripts so the demo mirrors the labelled test set. Times of day are preserved.
export const FEATURED: FeaturedCall[] = [
  {
    test_key: "call_16",
    agent: "Aakash Verma",
    language: "hinglish",
    ist_time: "16:20",
    days_ago: 1,
    duration_s: 140,
    loan_ref: "SF-PL-751426",
    segments: [
      A("Haan hello, Dinesh Bhosale bol rahe ho? Loan ke baare mein baat karni hai."),
      B("Haan, Dinesh bol raha hoon. Kaun bol raha hai?"),
      A("Aapke loan ki EMI do mahine se nahi aayi hai, 9000 rupaye ho gaye hain. Kab tak karoge?"),
      B("Sir, abhi dukaan mein ghata chal raha hai. Do-teen hafte ruk jaiye."),
      A("Do-teen hafte bahut zyada hain. Ek hafte mein kuch kijiye."),
      B("Ek hafte mein poora toh nahi ho payega. Aadha kar sakta hoon, 4500."),
      A("Theek hai, aadha ek hafte mein. Lekin dekhiye, kal tak payment nahi aaya toh main padosiyon ko bata dunga ki aap defaulter ho, society mein sabko pata chal jayega."),
      B("Arre, padosiyon ko kyun bata rahe ho? Meri izzat ka sawaal hai yahan."),
      A("Toh phir payment ki date pakki kijiye."),
      B("Agle Shanivaar ko. Pakka."),
      A("Shanivaar ko note kar liya. Baaki ka kya plan hai?"),
      B("Baaki ka mahine ke end tak. Aap ek baar likhit mein bhi bhej do."),
      A("Theek hai, SMS se bhej deta hoon."),
      B("Okay. Thank you."),
    ],
    violations: [
      {
        rule: "V8",
        seg: null,
        quote: null,
        explanation: "The agent did not state their own name or the lender's name in the first 60 seconds.",
        confidence: 0.91,
        detected_by: "both",
        reviewer: "confirmed",
      },
      {
        rule: "V5",
        seg: 6,
        quote: "society mein sabko pata chal jayega",
        explanation: "The agent threatens to tell the borrower's neighbours and society that the borrower is a defaulter.",
        confidence: 0.93,
        detected_by: "both",
      },
    ],
  },
  {
    test_key: "call_08",
    agent: "Imran Shaikh",
    language: "hinglish",
    ist_time: "17:35",
    days_ago: 2,
    duration_s: 140,
    loan_ref: "SF-PL-693218",
    segments: [
      A("Hello, main Imran Shaikh bol raha hoon Sahyog Finance se. Kya meri baat Rakesh Tiwari se ho rahi hai?"),
      B("Haan, boliye, Rakesh bol raha hoon."),
      A("Rakesh ji, aapki EMI pichhle ek mahine se pending hai, 5200 rupaye. Aaj payment kar rahe hain na?"),
      B("Nahi yaar, aaj nahi ho payega. Is hafte ke end tak dekhta hoon."),
      A("Pichhli baar bhi aapne yahi bola tha. Teen baar yahi bol chuke hain aap."),
      B("Haan, par iss baar sach mein koshish karunga. Dukaan band padi hai, maal nahi bik raha."),
      A("Sun, tu bada kamina aadmi hai, haramkhor, paise kha ke baitha hai aur bahaane bana raha hai."),
      B("Aap tameez se baat kijiye. Maine kabhi kisi ka paisa nahi khaya."),
      A("Ab sun, kal tak paisa nahi aaya toh recovery wale bhej dunga tere ghar pe, haddi tod denge teri, samjha?"),
      B("Ye kya bol rahe ho aap? Main complaint kar dunga."),
      A("Humara number aapke paas hai."),
      B("Haan, number hai mere paas. Main branch mein baat karunga."),
      A("Theek hai. Aaj shaam tak bataiye, kitna de sakte hain?"),
      B("Main aaj shaam tak kuch nahi kar sakta. Kal subah baat karte hain."),
      A("Theek hai. Kal subah 10 baje phone karunga."),
    ],
    violations: [
      {
        rule: "V2",
        seg: 6,
        quote: "tu bada kamina aadmi hai, haramkhor",
        explanation: "The agent calls the borrower a scoundrel and a freeloader.",
        confidence: 0.95,
        detected_by: "both",
        reviewer: "confirmed",
      },
      {
        rule: "V3",
        seg: 8,
        quote: "recovery wale bhej dunga tere ghar pe, haddi tod denge teri",
        explanation: "The agent threatens to send recovery men to the borrower's home and break the borrower's bones.",
        confidence: 0.97,
        detected_by: "both",
      },
    ],
  },
  {
    test_key: "call_07",
    agent: "Rohit Patil",
    language: "hinglish",
    ist_time: "21:40",
    days_ago: 3,
    duration_s: 105,
    loan_ref: "SF-PL-502183",
    segments: [
      A("Namaste, main Rohit Patil bol raha hoon Sahyog Finance se. Kya meri baat Vikas Rane ji se ho rahi hai?"),
      B("Haan, Vikas bol raha hoon. Itni raat ko call kar rahe ho? Dekho time kya hua hai."),
      A("Sir, din bhar aapka number busy aa raha tha, isliye abhi call kiya. Aapki EMI chaar hafte se pending hai, 7000 rupaye."),
      B("Haan, pata hai. Iss mahine kuch kharche ho gaye, bhai ki shaadi thi ghar mein. Agle mahine ki 10 tarikh tak kar dunga."),
      A("10 tarikh? Sir, ye toh bahut door hai. Is hafte kuch nahi ho sakta?"),
      B("Sir, abhi nahi ho sakta. Please samjho."),
      A("Theek hai sir, phir main aapke office ke number par hi call karta hoon, office mein sabko bata denge ki loan ka kya scene hai, phir dekhte hain."),
      B("Arre, office mein kyun bata rahe ho? Mera boss sunega toh meri naukri jaayegi."),
      A("Toh aap hi bataiye sir, kab tak kuch ho payega?"),
      B("Please, aisa mat karo. Main koshish karta hoon, parson tak kuch bhar deta hoon."),
      A("Theek hai, Guruwar ko 5000 rupaye. Baaki 2000 10 tarikh ko."),
      B("Haan, yehi final hai. Ab rakhta hoon, bachche so rahe hain."),
      A("Theek hai sir. Dhanyavaad."),
    ],
    violations: [
      {
        rule: "V1",
        seg: null,
        quote: null,
        explanation: "The call started at 21:40 IST, outside the permitted window of 08:00 to 19:00, and the borrower did not ask for that time.",
        confidence: 1,
        detected_by: "metadata",
        reviewer: "confirmed",
      },
      {
        rule: "V5",
        seg: 6,
        quote: "office mein sabko bata denge",
        explanation: "The agent threatens to tell the borrower's colleagues about the loan.",
        confidence: 0.88,
        detected_by: "both",
      },
    ],
  },
  {
    test_key: "call_14",
    agent: "Imran Shaikh",
    language: "hinglish",
    ist_time: "11:10",
    days_ago: 4,
    duration_s: 180,
    loan_ref: "SF-PL-429067",
    segments: [
      A("Namaste, main Imran Shaikh bol raha hoon Sahyog Finance se. Kya meri baat Naveen Joshi ji se ho rahi hai?"),
      B("Haan, boliye. Naveen bol raha hoon."),
      A("Naveen ji, aapki do EMI pending hain, kul 16000 rupaye. Aaj kuch ho sakta hai?"),
      B("Sir, abhi toh thoda mushkil hai. Pichhle mahine naukri chali gayi thi, ab naya kaam shuru kiya hai."),
      A("Achha. Naveen ji, seedhi baat bataun, main RBI ke recovery cell se bol raha hoon, aapka case humare paas aa chuka hai."),
      B("RBI ke recovery cell se? Par aapne toh abhi Sahyog Finance bola tha."),
      A("Haan, ek hi baat hai. Aap bas EMI ka intezaam kijiye."),
      B("Sir, mujhe sirf ek mahina chahiye. Pehli salary aane tak."),
      A("Ek mahina nahi milega. Kal police aa jayegi aur jail bhej denge, aap soch lijiye."),
      B("Police? Sirf do EMI ke liye? Mujhe toh koi notice bhi nahi mila."),
      A("Aap bataiye, paisa kahan se laayenge?"),
      B("Main apne mama se maang ke dekhta hoon. Shaam tak bata deta hoon."),
      A("Theek hai. Shaam 5 baje tak bata dijiyega."),
      B("Ji, theek hai. Main call karta hoon."),
    ],
    violations: [
      {
        rule: "V7",
        seg: 4,
        quote: "main RBI ke recovery cell se bol raha hoon",
        explanation: "The agent falsely claims to be calling from the RBI.",
        confidence: 0.94,
        detected_by: "both",
      },
      {
        rule: "V4",
        seg: 8,
        quote: "Kal police aa jayegi aur jail bhej denge",
        explanation: "The agent claims police will come tomorrow and send the borrower to jail over two missed EMIs.",
        confidence: 0.96,
        detected_by: "both",
        reviewer: "confirmed",
      },
    ],
  },
  {
    test_key: "call_05",
    agent: "Rohit Patil",
    language: "marathi",
    ist_time: "09:45",
    days_ago: 5,
    duration_s: 180,
    loan_ref: "SF-PL-189524",
    segments: [
      A("नमस्कार, मी रोहित पाटील बोलतोय सहयोग फायनान्स मधून. गणेश पवार यांच्याशी बोलतोय का?"),
      B("हो, बोला."),
      A("तुमच्या पर्सनल लोनचा हप्ता पंधरा दिवसांपासून थकलेला आहे, 6000 रुपये. कधी भरताय?"),
      B("साहेब, गावी शेतातलं पीक गेलं यावर्षी. थोडा वेळ द्या."),
      A("किती वेळ हवा आहे तुम्हाला? पुढच्या आठवड्यापर्यंत होईल का?"),
      B("पुढच्या आठवड्यात नाही होणार. महिनाभर तरी लागेल."),
      A("महिनाभर? नाही नाही, ते चालणार नाही. मला स्पष्ट सांगतो, उद्या पोलीस तुमच्या दारात येतील आणि तुम्हाला तुरुंगात जावं लागेल."),
      B("साहेब, काय बोलताय? एवढ्याशा हप्त्यासाठी पोलीस? मला काही नोटीस आलेली नाही. मी काय गुन्हा केला?"),
      A("मी फक्त तुम्हाला माहिती देतोय. तुम्ही काय ते आज संध्याकाळपर्यंत कळवा."),
      B("ठीक आहे, मी भावाकडून पैसे मागून बघतो आणि संध्याकाळी फोन करतो."),
      A("किती रक्कम भरू शकाल? पूर्ण सहा हजार की थोडी कमी?"),
      B("पूर्ण सहा हजार जमवणं अवघड आहे. चार हजार संध्याकाळपर्यंत भरू शकतो आणि उरलेले दोन हजार पुढच्या आठवड्यात."),
      A("ठीक आहे, मी चार हजार आज आणि दोन हजार पुढच्या आठवड्यात असं लिहून घेतो."),
      B("ठीक आहे, नमस्कार."),
    ],
    violations: [
      {
        rule: "V4",
        seg: 6,
        quote: "उद्या पोलीस तुमच्या दारात येतील",
        explanation: "The agent claims police will arrive at the borrower's door tomorrow and that the borrower will go to jail over a missed instalment.",
        confidence: 0.89,
        detected_by: "both",
      },
    ],
  },
  {
    test_key: "call_22",
    agent: "Pooja Yadav",
    language: "hinglish",
    ist_time: "19:00",
    days_ago: 6,
    duration_s: 105,
    loan_ref: "SF-PL-258037",
    segments: [
      A("Namaste, main Pooja Yadav bol rahi hoon Sahyog Finance se. Kya meri baat Irfan Ansari ji se ho rahi hai?"),
      B("Haan, Irfan bol raha hoon. Boliye."),
      A("Irfan ji, aapke personal loan ki ek EMI pending hai, 7500 rupaye. Kya aaj ho sakti hai?"),
      B("Aaj nahi ho payegi madam. Kal dopahar tak kar dunga. Aaj raat kuch paisa aane wala hai."),
      A("Theek hai. Kal dopahar kitne baje tak?"),
      B("Do baje tak. Aur madam, mera ek aur number hai. Agar mera ye number na uthe toh aap us par try kar sakti hain. Likh lijiye. [PHONE]."),
      A("Main repeat karti hoon: [PHONE]. Kya ye sahi hai?"),
      B("Haan, bilkul sahi hai."),
      A("Theek hai, main record mein update kar deti hoon. Kya aap is number par kisi bhi time call receive kar sakte hain?"),
      B("Din mein 10 se 7 baje ke beech mein. Raat ko nahi, bachche so jaate hain."),
      A("Samajh gayi. Main usi time par call karungi."),
      B("Shukriya. Aur madam, late payment charge kitna hota hai?"),
      A("Wo aapke agreement mein likha hai. Exact figure aap app mein loan details mein dekh sakte hain."),
      B("Achha, app mein dekh lunga. Dhanyavaad."),
      A("Aapka bhi dhanyavaad Irfan ji. Kal dopahar 2 baje ka payment note kar liya hai."),
    ],
    violations: [],
  },
];
