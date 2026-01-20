# Outreach Reality: Who, Why, and What

**Date:** January 28, 2025  
**Status:** Ready for Outreach (with contact finding needed)

---

## 1. WHO YOU'RE REACHING OUT TO

### **28 Principal Investigators** from ClinicalTrials.gov

**What We Have:**
- ✅ **PI Names** (28)
- ✅ **Institutions** (28)
- ✅ **Trial Titles** (28)
- ✅ **NCT IDs** (28)
- ❌ **Email Addresses** (0 - need to find manually)

**Who They Are:**
- Principal Investigators running **ovarian cancer clinical trials**
- Trials **mention CA-125** in descriptions
- Trials are **RECRUITING** or **ACTIVE_NOT_RECRUITING**
- They're **active researchers** in ovarian cancer

**Sample Contacts:**
1. **Ka Yu Tse, MBBS, MMedSc, PhD, FRCOG**
   - Institution: The University of Hong Kong
   - Trial: NCT07022535

2. **David Alberts, MD**
   - Institution: [From trial data]
   - Trial: [NCT ID from data]

3. **Dae-Yeon Kim**
   - Institution: [From trial data]
   - Trial: [NCT ID from data]

4. **Laurent Brard, MD, PhD**
   - Institution: [From trial data]
   - Trial: [NCT ID from data]

*(See `ctgov_pi_contacts.json` for complete list)*

---

## 2. WHY YOU'RE REACHING OUT

### **KELIM Biomarker Validation Study**

**What is KELIM?**
- **KELIM** = CA-125 Elimination Rate
- Calculated from **serial CA-125 measurements** during first 100 days of platinum-based chemotherapy
- **Predicts platinum resistance**: Low KELIM → PFI < 6 months (platinum resistant)

**Why Validation is Needed:**
- KELIM has shown promise but needs independent validation
- Will enable clinical adoption if validated
- Requires multiple cohorts for robust validation

**What Data You Need:**
- ✅ **Serial CA-125 measurements** (≥2 per patient, ideally 3-4)
- ✅ **Platinum-free interval (PFI)** outcomes or dates
- ✅ **Treatment information** (platinum agent, dates)
- ✅ **Minimum 50-100 patients** for validation

**Why These PIs Have What You Need:**
- Their trials **monitor CA-125** (mentioned in trial descriptions)
- They're running **ovarian cancer trials** (relevant population)
- They likely collect **serial CA-125** as standard monitoring
- They track **progression outcomes** (can calculate PFI)

---

## 3. WHAT YOU'RE SAYING

### **Email Subject:**
```
Data Sharing Request for KELIM Biomarker Validation Study
```

### **Email Message Template:**

```
Dear Dr. {PI Name},

I hope this email finds you well. I am reaching out regarding a research collaboration opportunity for validating the KELIM (CA-125 elimination rate) biomarker for predicting platinum resistance in ovarian cancer.

**About the Study:**
We are conducting a validation study of the KELIM biomarker, which uses serial CA-125 measurements during the first 100 days of platinum-based chemotherapy to predict platinum-free interval (PFI < 6 months). This biomarker has shown promise in previous studies but requires validation across multiple independent cohorts.

**What We Need:**
- Patient-level data with serial CA-125 measurements (≥2 per patient, ideally 3-4)
- Platinum-free interval (PFI) outcomes or dates to calculate PFI
- Treatment information (platinum agent used, treatment dates)
- Minimum of 50-100 patients for statistical validation

**Benefits of Collaboration:**
- Co-authorship on resulting publication
- Access to validated biomarker for your research
- Contribution to advancing ovarian cancer treatment
- Recognition in biomarker validation literature

**Data Requirements:**
- Serial CA-125 measurements (preferred: every cycle, q3weeks)
- Treatment dates and platinum agent used
- Progression dates or PFI outcomes
- De-identified patient data (IRB compliant)

I noticed your trial "{Trial Title}" (NCT{NCT_ID}) involves CA-125 monitoring, which makes it an ideal candidate for this validation study.

We would be happy to discuss:
- Data sharing agreements
- IRB considerations
- Co-authorship details
- Any questions you may have

Thank you for your consideration. I look forward to hearing from you.

Best regards,
[Your Name]
[Your Affiliation]
[Your Contact Information]
```

### **Key Points:**
1. **Mutual benefit** - Co-authorship opportunity
2. **Low burden** - They already have the data
3. **High impact** - Advancing ovarian cancer treatment
4. **Specific ask** - Clear data requirements
5. **Personalization** - Mention their specific trial (NCT ID)

---

## 4. HOW TO FIND CONTACT INFORMATION

Since email addresses weren't extracted, you'll need to find them:

### **Method 1: Institution Websites**
1. Go to institution website
2. Search for PI name in faculty directory
3. Find email address

### **Method 2: ClinicalTrials.gov**
1. Go to trial page (using NCT ID)
2. Check "Contacts and Locations" section
3. May have email or phone for contact

### **Method 3: Research Databases**
1. PubMed - Search for PI name + institution
2. ResearchGate - PI profile may have contact
3. LinkedIn - Professional contact
4. Google Scholar - Often has institutional email

### **Method 4: Institutional Email Pattern**
- Common patterns: `firstname.lastname@institution.edu`
- Or: `firstinitial.lastname@institution.edu`
- Check institution's email directory

---

## 5. OUTREACH STRATEGY

### **Recommended Approach:**

1. **Prioritize Contacts**
   - Start with well-known institutions (easier to find contacts)
   - Prioritize larger trials (more patients)
   - Focus on academic institutions (higher collaboration likelihood)

2. **Find Contact Information**
   - Use methods above to find emails
   - Update `d15_pi_contact_database.json` with found emails
   - Track in `d15_outreach_tracking_template.csv`

3. **Personalize Each Email**
   - Mention their specific trial title and NCT ID
   - Reference their institution's research
   - Customize based on trial phase/type

4. **Timeline**
   - **Week 1:** Find contacts for top 10-15 PIs, send emails
   - **Week 2:** Find remaining contacts, follow up on non-responders
   - **Week 3-4:** Send to all contacts, follow up
   - **Week 4+:** Continue follow-ups

### **Expected Outcomes:**

- **Response Rate:** 30-50% (8-14 responses)
- **Data Sharing Rate:** 10-25% (3-7 datasets)
- **Timeline:** 1-2 weeks for initial responses, 4-6 weeks for data sharing

---

## 6. FILES REFERENCE

- **Contact Database:** `ctgov_pi_contacts.json` (28 PIs with names, institutions, trials)
- **Outreach Templates:** `d15_pi_outreach_templates.md`
- **Tracking Template:** `d15_outreach_tracking_template.csv`
- **This Guide:** `OUTREACH_REALITY.md`

---

## SUMMARY

**WHO:** 28 Principal Investigators (names, institutions, trials known; emails need finding)

**WHY:** KELIM biomarker validation - need serial CA-125 + PFI data

**WHAT:** Requesting data sharing with co-authorship offer

**NEXT STEP:** Find email addresses for PIs, then send personalized outreach emails

---

**Last Updated:** January 28, 2025





