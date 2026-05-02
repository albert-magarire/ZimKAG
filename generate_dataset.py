"""
Dataset generator for NLP contract risk classification.
Schema: text, risk_level, clause_type, one_sided, jurisdiction, contract_type, notes
risk_level: high | medium | low | opportunity | neutral
"""
import csv, random, re

random.seed(42)

# ── helpers ──────────────────────────────────────────────────────────────────

OLD_LABEL_MAP = {'0': 'high', '1': 'low', '2': 'medium', '3': 'neutral'}
OLD_CAT_MAP = {
    'payment': 'payment', 'administrative': 'administrative',
    'regulatory_change': 'regulatory', 'site_conditions': 'site_conditions',
    'liquidated_damages': 'delay', 'currency': 'payment',
    'community_unrest': 'force_majeure',
}
REAL_SOURCES = {
    'RAM Solutions Subcontract Agreement 2.pdf': ('ZW', 'bespoke'),
    'Zimplats_Masimba_Phase2A_Contract.pdf':     ('ZW', 'bespoke'),
    'Casecnan Multipurpose Irrigation Contract.pdf': ('PH', 'bespoke'),
    'Pitch Carpenters Agreement.docx':           ('ZW', 'bespoke'),
    'Elegance_Ivy_Independent_Service_Contract.pdf': ('ZW', 'bespoke'),
}

def map_real_row(row):
    src = row[3].strip()
    if src not in REAL_SOURCES:
        return None
    jur, ctype = REAL_SOURCES[src]
    rl = OLD_LABEL_MAP.get(row[1].strip(), 'medium')
    ct = OLD_CAT_MAP.get(row[2].strip(), row[2].strip() or 'administrative')
    one_sided = 'true' if rl in ('high',) else ('false' if rl in ('neutral','low') else 'false')
    note = ''
    if rl == 'high':   note = 'Clause creates significant risk for subcontractor; one-sided in favour of contractor/employer.'
    if rl == 'neutral': note = 'Heading or procedural clause; no material risk allocation.'
    return [row[0].strip(), rl, ct, one_sided, jur, ctype, note]

# ── clause libraries ──────────────────────────────────────────────────────────
# Each entry: (text, risk_level, clause_type, one_sided, jurisdiction, contract_type, notes)

JCT_HIGH = [
    ("The Contractor shall pay liquidated and ascertained damages at the rate stated in the Contract Particulars for every week or part week during which Practical Completion is delayed beyond the Completion Date, without limit as to time or amount.",
     "high","delay","true","UK","JCT","Uncapped LADs with no causal link required; significant financial exposure for contractor."),
    ("The Employer may deduct from any sum due to the Contractor any amount the Employer considers due from the Contractor under or in connection with the Contract, whether or not such amount has been ascertained.",
     "high","payment","true","UK","JCT","Unrestricted set-off right without requirement for formal notice or ascertainment; exposes contractor to arbitrary deductions."),
    ("Any extension of time application by the Contractor must be made within 7 days of the occurrence of the relevant event, failing which the Contractor shall be deemed to have waived its entitlement.",
     "high","delay","true","UK","JCT","Extremely short notice period; strict waiver provision with no discretion for Engineer/Architect."),
    ("The Contractor warrants that it has independently verified all information provided by the Employer and accepts full responsibility for any errors or discrepancies in the Contract Documents.",
     "high","indemnity","true","UK","JCT","Contractor assumes employer's design risk; eliminates implied warranty on employer-provided information."),
    ("The Employer may terminate the Contractor's employment at will and without cause upon giving 7 days' written notice, whereupon the Contractor shall be entitled only to payment for work properly executed.",
     "high","termination","true","UK","JCT","At-will termination without compensation for loss of anticipated profit or demobilisation costs; highly one-sided."),
    ("The Contractor shall indemnify and hold harmless the Employer against all claims, losses and liabilities arising out of or in connection with the Works, whether or not caused by the Contractor's negligence.",
     "high","indemnity","true","UK","JCT","Indemnity without negligence requirement effectively makes contractor an insurer for all site events."),
    ("The Architect's decision on any matter concerning the quality or quantity of the Works shall be final and binding and shall not be subject to review in any dispute resolution proceedings.",
     "high","dispute","true","UK","JCT","Ousts contractor's right to challenge Architect's decisions; contrary to HGCRA principles."),
    ("Retention shall be held by the Employer in its general account and shall not attract interest; no obligation to place retention in a separate trust account arises.",
     "high","payment","true","UK","JCT","Retention is not ring-fenced; contractor has no protection if employer becomes insolvent."),
    ("The Contractor shall not be entitled to any additional payment or extension of time arising from any ground conditions, howsoever arising, whether foreseeable or unforeseeable.",
     "high","site_conditions","true","UK","JCT","Full unforeseeable ground risk passed to contractor without any site investigation warranty from employer."),
    ("Practical Completion shall not be certified unless all snagging items and outstanding works have been fully completed to the Employer's Agent's absolute satisfaction.",
     "high","delay","true","UK","JCT","Subjective practical completion test prevents contractor triggering LAD stop; unlimited retention period."),
    ("The Contractor shall be liable for consequential, indirect and economic loss suffered by the Employer arising out of any breach, delay or defect, without financial cap.",
     "high","indemnity","true","UK","JCT","Uncapped consequential loss liability is commercially unacceptable and uninsurable."),
    ("All Intellectual Property created during the Works shall vest exclusively in the Employer upon creation without further payment to the Contractor.",
     "high","variation","true","UK","JCT","IP assignment without compensation; contractor loses rights to proprietary methods and designs."),
    ("The Contractor shall not suspend work for non-payment unless it has given 28 days' prior written notice and obtained a court order confirming the sum is due.",
     "high","payment","true","UK","JCT","Effectively removes contractor's statutory suspension right under HGCRA by imposing impractical preconditions."),
    ("Any variation instructed by the Employer shall be valued by the Employer's Quantity Surveyor, whose valuation shall be final and binding on the Contractor.",
     "high","variation","true","UK","JCT","Removes contractor's right to challenge variation valuations through dispute resolution."),
    ("The Contractor shall complete the Works and all snagging within the Defects Liability Period without any entitlement to prolongation costs or disruption claims.",
     "high","delay","true","UK","JCT","Contractor bears full prolongation and disruption costs even where caused by employer actions."),
    ("Force majeure shall not excuse the Contractor from any obligation under this Contract, including payment of liquidated damages during periods of force majeure.",
     "high","force_majeure","true","UK","JCT","Force majeure excluded as a relief mechanism; contractor remains liable for LADs during force majeure events."),
    ("The Employer may at any time instruct the removal of the Contractor's key personnel, and the Contractor shall have no right to object or seek compensation for the disruption caused.",
     "high","variation","true","UK","JCT","Employer can disrupt contractor's team without justification or compensation."),
    ("The Contractor accepts all risk of currency fluctuation throughout the Contract Period; no adjustment mechanism applies to the Contract Sum in respect of exchange rate movements.",
     "high","payment","true","UK","JCT","Full currency risk transferred to contractor in long-duration international projects."),
    ("Payment of the final account shall only become due when the Employer has received all as-built drawings, O&M manuals, warranties and training certificates in a form satisfactory to the Employer.",
     "high","payment","true","UK","JCT","Final payment held hostage to administrative deliverables, giving employer disproportionate leverage after practical completion."),
    ("The Contractor shall be liable for the full cost of any re-testing or re-inspection required whether or not the works are found to be compliant upon re-inspection.",
     "high","indemnity","true","UK","JCT","Contractor pays re-inspection costs even when subsequent test passes; creates financial deterrent to exercising inspection rights."),
    ("No interim payment shall be due to the Contractor until the Employer has received and verified the Contractor's application; the Employer shall have 60 days to make such verification.",
     "high","payment","true","UK","JCT","Verification period far exceeds HGCRA requirements; effectively extends payment cycle to 75+ days."),
    ("The Contractor shall rectify any defect notified during the Defects Liability Period within 3 days of notification, failing which the Employer may engage others and recover costs at a premium rate of 150% of the cost incurred.",
     "high","warranty","true","UK","JCT","Impossibly short rectification window; premium rate recovery is punitive and unjustifiable."),
    ("All disputes shall be referred to the Employer's Representative for determination, and such determination shall be binding on the Contractor for the duration of the project.",
     "high","dispute","true","UK","JCT","Employer's own representative acting as adjudicator creates conflict of interest and denies contractor independent remedy."),
]

JCT_MEDIUM = [
    ("The Contractor shall give written notice to the Architect within 28 days of the occurrence of a Relevant Event and shall provide particulars within a further 14 days.",
     "medium","delay","false","UK","JCT","Standard EOT notice provisions; strict but not unreasonable."),
    ("The Contractor shall take out and maintain Contractors All Risks insurance in the joint names of the Employer and Contractor for the full reinstatement value of the Works.",
     "medium","indemnity","false","UK","JCT","Standard insurance requirement; risk allocation is balanced."),
    ("If the Contractor desires to make any variation to the design or specification, it shall submit a formal request to the Employer's Agent, who may consent or refuse at their reasonable discretion.",
     "medium","variation","false","UK","JCT","Variation approval subject to reasonable discretion; some restriction on contractor flexibility."),
    ("The Contractor shall keep and maintain proper books of account relating to the Works and shall make them available for inspection by the Employer's Quantity Surveyor on 48 hours' notice.",
     "medium","payment","false","UK","JCT","Open-book accounting obligation; some administrative burden but not unusual."),
    ("Extension of time shall be granted where the Contractor demonstrates on the balance of probabilities that a Relevant Event caused critical delay to Practical Completion.",
     "medium","delay","false","UK","JCT","Causal link and balance of probabilities test is standard but requires robust programming evidence."),
    ("The Defects Liability Period shall be 12 months from the date of Practical Completion during which the Contractor shall rectify defects notified by the Employer within 21 days.",
     "medium","warranty","false","UK","JCT","Standard DLP provision; 21-day notice-to-rectify window is reasonable."),
    ("The Contractor shall submit a detailed construction programme within 14 days of the Date of Possession and shall update it monthly or following any significant change.",
     "medium","delay","false","UK","JCT","Programme obligation is standard; failure to comply may affect EOT entitlement."),
    ("Variations shall be valued using the rates and prices in the Contract Bills where applicable, and where not applicable, at fair rates and prices to be agreed.",
     "medium","variation","false","UK","JCT","Bilateral agreement mechanism for variation valuation; balanced but subject to dispute."),
    ("The Employer may withhold payment of any certified sum provided it issues a Pay Less Notice not later than the prescribed period before the final date for payment.",
     "medium","payment","false","UK","JCT","HGCRA-compliant pay less notice mechanism; contractor has clear right to challenge."),
    ("The Contractor shall comply with all CDM 2015 requirements as Principal Contractor and shall bear the cost of such compliance unless expressly stated otherwise.",
     "medium","regulatory","false","UK","JCT","CDM compliance is a statutory duty; cost allocation is standard practice."),
    ("Retention shall be at the rate of 5% until Practical Completion, reducing to 2.5% thereafter, and shall be released at the end of the Defects Liability Period.",
     "medium","payment","false","UK","JCT","Standard retention regime; rates are at the higher end of market practice."),
    ("The Contractor shall not assign this Contract or any part of it without the prior written consent of the Employer, which shall not be unreasonably withheld or delayed.",
     "medium","administrative","false","UK","JCT","Anti-assignment clause with reasonableness qualifier; balanced provision."),
    ("The Employer's Agent may issue instructions requiring the Contractor to open up work for inspection; where the work is found to be in accordance with the Contract, the cost shall be added to the Contract Sum.",
     "medium","variation","false","UK","JCT","Cost recovery mechanism for compliant open-up is fair; risk of disruption remains."),
    ("The Contractor shall provide a performance bond in the sum of 10% of the Contract Sum within 14 days of execution of the Contract.",
     "medium","administrative","false","UK","JCT","Performance bond at 10% is at the higher end; bond cost is a contractor risk."),
    ("Dispute shall first be referred to mediation; if not resolved within 28 days either party may refer the dispute to adjudication in accordance with the Scheme for Construction Contracts.",
     "medium","dispute","false","UK","JCT","Tiered dispute resolution with adjudication backstop; balanced and HGCRA compliant."),
    ("The Contractor shall not be entitled to loss of profit on omitted works where variations reduce the scope of the Contract.",
     "medium","variation","true","UK","JCT","Exclusion of loss of profit on omissions is common but limits contractor's commercial protection."),
    ("Interest shall accrue on overdue payments at a rate of 5% above Bank of England Base Rate from the final date for payment.",
     "medium","payment","false","UK","JCT","Standard interest provision; rate is adequate but not punitive."),
    ("The Contractor shall notify the Employer within 14 days of becoming aware of any circumstance that may give rise to a compensation event under clause 60.",
     "medium","delay","false","UK","JCT","Notice obligation is standard; failure may reduce entitlement in practice."),
    ("Sub-contracting of portions of the Works exceeding 25% of the Contract Sum requires prior written consent from the Employer's Agent.",
     "medium","administrative","false","UK","JCT","Sub-contracting threshold consent requirement is commercially acceptable."),
    ("The Contractor shall comply with the Employer's site rules and environmental management plan as updated from time to time during the Contract Period.",
     "medium","regulatory","false","UK","JCT","Compliance with evolving site rules creates some uncertainty but is standard on managed sites."),
]

JCT_LOW = [
    ("The Employer shall give the Contractor possession of the Site on the Date of Possession stated in the Contract Particulars.",
     "low","administrative","false","UK","JCT","Standard possession provision; balanced obligation on employer."),
    ("Where the Employer fails to give possession of the Site on the Date of Possession, such failure shall be a Relevant Matter entitling the Contractor to loss and expense.",
     "low","delay","false","UK","JCT","Contractor protected for employer's failure to give possession."),
    ("The Architect shall issue Interim Payment Certificates at the intervals stated in the Contract Particulars, and the Employer shall pay within 14 days of the due date.",
     "low","payment","false","UK","JCT","Clear payment timeline; HGCRA compliant."),
    ("The Contractor shall be entitled to an extension of time for completion of the Works where completion is or is likely to be delayed by a Relevant Event.",
     "low","delay","false","UK","JCT","Standard EOT entitlement clause; contractor protected for specified relief events."),
    ("Either party may terminate this Contract on the insolvency of the other party.",
     "low","termination","false","UK","JCT","Standard insolvency termination clause; mutual right is balanced."),
    ("The parties shall attempt to resolve any dispute by negotiation within 28 days of written notice of the dispute.",
     "low","dispute","false","UK","JCT","Negotiation first step is standard and commercially sensible."),
    ("The Contractor shall comply with all applicable laws and regulations in carrying out the Works.",
     "low","regulatory","false","UK","JCT","General compliance obligation; standard and uncontroversial."),
    ("The Employer shall appoint an Employer's Agent to act on its behalf in administering the Contract.",
     "low","administrative","false","UK","JCT","Standard appointment provision; defines contract administration structure."),
    ("The Contractor shall maintain a site diary recording daily weather conditions, labour deployed and progress of the Works.",
     "low","administrative","false","UK","JCT","Record-keeping obligation; protects both parties in claims situations."),
    ("All notices under this Contract shall be in writing and may be served by email, fax, hand delivery or first class post.",
     "low","administrative","false","UK","JCT","Clear service of notice provision; balanced and practical."),
    ("The Contractor shall attend progress meetings at such intervals as the Employer's Agent may reasonably require.",
     "low","administrative","false","UK","JCT","Standard meeting obligation; reasonable frequency qualifier protects contractor."),
    ("The Employer shall pay the final balance of the Contract Sum within 28 days of the issue of the Final Certificate.",
     "low","payment","false","UK","JCT","Clear final payment timeline; balanced obligation."),
    ("The Contractor shall provide copies of all required insurances to the Employer within 7 days of request.",
     "low","indemnity","false","UK","JCT","Standard insurance evidence obligation; reasonable timescale."),
    ("The Contractor shall ensure the Works are carried out in a good and workmanlike manner using materials of the quality specified.",
     "low","warranty","false","UK","JCT","Standard workmanship obligation; fundamental but balanced."),
    ("Where the Contract Documents are inconsistent, the order of precedence shall be: the Agreement, then the Conditions, then the Employer's Requirements, then the Contractor's Proposals.",
     "low","administrative","false","UK","JCT","Standard precedence clause; provides clarity in case of conflict."),
    ("The Contractor shall take all reasonable precautions to prevent nuisance, disturbance or inconvenience to occupiers of adjacent properties.",
     "low","regulatory","false","UK","JCT","Reasonable neighbour obligation; qualified by 'reasonable precautions'."),
    ("The Contractor shall provide and maintain adequate lighting on the Site during working hours.",
     "low","site_conditions","false","UK","JCT","Standard site obligation; low risk."),
    ("The Employer shall provide such information as the Contractor may reasonably require to carry out the Works.",
     "low","administrative","false","UK","JCT","Mutual information obligation; protects contractor's right to information."),
    ("The parties confirm that this Contract constitutes the entire agreement between them in respect of the Works and supersedes all prior negotiations.",
     "low","administrative","false","UK","JCT","Entire agreement clause; standard contract formation provision."),
    ("The Contractor shall be entitled to apply for interim payment on a monthly basis throughout the Contract Period.",
     "low","payment","false","UK","JCT","Monthly interim payment right; standard cash flow provision."),
]

JCT_OPPORTUNITY = [
    ("Where the Employer fails to issue a payment notice or pay less notice by the prescribed date, the sum stated in the Contractor's payment application shall become the sum due.",
     "opportunity","payment","true","UK","JCT","Default payment mechanism under HGCRA; contractor's application becomes notified sum if employer fails to serve notice."),
    ("The Contractor shall be entitled to recover finance charges and legal costs incurred in pursuing overdue payments as a debt due under this Contract.",
     "opportunity","payment","false","UK","JCT","Express right to recover finance costs and legal fees; strengthens contractor's cash flow protection."),
    ("Where the Employer issues an omission instruction solely to have the omitted work carried out by another contractor, the Contractor shall be entitled to loss of profit on the omitted work.",
     "opportunity","variation","true","UK","JCT","Anti-canon clause protecting contractor from employer using omission instructions to divert work to others."),
    ("The Contractor may suspend performance of the whole or any part of the Works where a payment is overdue, by giving 7 days' written notice to the Employer.",
     "opportunity","payment","false","UK","JCT","HGCRA suspension right expressly preserved; contractor has clear mechanism to address non-payment."),
    ("Where a Relevant Event also causes the Contractor to incur additional costs, the Contractor shall be entitled to both extension of time and reimbursement of loss and expense.",
     "opportunity","delay","false","UK","JCT","Dual entitlement for time and money on relevant matters; balanced and contractor-friendly."),
    ("The Contractor shall be entitled to claim direct loss and expense for any act, omission or default of the Employer or Employer's Agent that causes disruption to the Works.",
     "opportunity","delay","false","UK","JCT","Broad disruption claim entitlement covering employer defaults; protects contractor's commercial position."),
    ("The Employer's obligation to provide information on time is a condition precedent to the Contractor's obligation to maintain the programme; late information shall entitle the Contractor to an extension of time.",
     "opportunity","delay","false","UK","JCT","Information provision as condition precedent; strong protection where employer delays drawings or instructions."),
    ("Where the final account value exceeds the Contract Sum by more than 15%, the Contractor shall be entitled to re-price preliminaries and time-related items.",
     "opportunity","payment","false","UK","JCT","Preliminaries re-pricing right on substantial scope increase; protects contractor on poorly scoped projects."),
    ("Any acceleration instruction by the Employer shall constitute a variation entitling the Contractor to additional payment for overtime, additional resources and loss of productivity.",
     "opportunity","variation","true","UK","JCT","Acceleration as a paid variation; prevents employer from demanding acceleration without compensation."),
    ("The Contractor shall retain title to all temporary works and equipment on site until paid in full; the Employer acknowledges no lien or right of retention over such items.",
     "opportunity","payment","true","UK","JCT","Romalpa-style retention of title clause; protects contractor's plant and equipment on employer insolvency."),
]

JCT_NEUTRAL = [
    ("SECTION 1 – DEFINITIONS AND INTERPRETATION","neutral","administrative","false","UK","JCT","Contract heading/section marker."),
    ("In this Contract, the following terms have the meanings given to them below unless the context otherwise requires.",
     "neutral","administrative","false","UK","JCT","Standard definitions introduction."),
    ("SECTION 2 – CONTRACTOR'S OBLIGATIONS","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 3 – CONTROL OF THE WORKS","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 4 – PAYMENT","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 5 – VARIATIONS","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 6 – INJURY, DAMAGE AND INSURANCE","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 7 – ASSIGNMENT, THIRD PARTY RIGHTS AND COLLATERAL WARRANTIES","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 8 – TERMINATION","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("SECTION 9 – SETTLEMENT OF DISPUTES","neutral","administrative","false","UK","JCT","Contract section heading."),
    ("'Architect' means the person named as such in the Contract Particulars or any replacement appointed by the Employer.",
     "neutral","administrative","false","UK","JCT","Standard definition; identifies key contract administrator."),
    ("'Contract Sum' means the sum named in Article 2, as adjusted in accordance with the provisions of this Contract.",
     "neutral","administrative","false","UK","JCT","Standard definition of contract price."),
    ("'Practical Completion' means the stage at which the Works are practically complete as certified by the Architect.",
     "neutral","administrative","false","UK","JCT","Standard definition; pivotal trigger for retention release and LAD cessation."),
    ("'Completion Date' means the date stated in the Contract Particulars for completion of the Works, as adjusted by any extension of time granted under this Contract.",
     "neutral","administrative","false","UK","JCT","Standard definition."),
    ("'Relevant Event' means any of the events listed in clause 2.29 of these Conditions.",
     "neutral","administrative","false","UK","JCT","Cross-reference definition; no risk allocation."),
    ("The Contract shall be governed by and construed in accordance with the law of England and Wales.",
     "neutral","administrative","false","UK","JCT","Governing law clause; standard for UK-based JCT contract."),
    ("Any provision of this Contract found to be void or unenforceable shall be severed without affecting the remaining provisions.",
     "neutral","administrative","false","UK","JCT","Severability clause; standard boilerplate."),
    ("This Contract may be executed in counterparts, each of which when executed shall constitute an original.",
     "neutral","administrative","false","UK","JCT","Counterparts execution; standard administrative provision."),
    ("The Contractor shall commence the Works on the Date of Possession and shall proceed regularly and diligently.",
     "neutral","administrative","false","UK","JCT","Commencement obligation; standard."),
    ("Words importing the singular include the plural and vice versa; words importing any gender include all genders.",
     "neutral","administrative","false","UK","JCT","Standard interpretation provision."),
]

NEC4_HIGH = [
    ("The Contractor accepts the risk of any event which the Contractor could have foreseen at the Contract Date and which affects the Contractor's ability to Provide the Works.",
     "high","site_conditions","true","UK","NEC4","Ouster of compensation events for foreseeable risk; broad contractor risk assumption."),
    ("The Project Manager may instruct the Contractor to stop or not start any work without giving a reason, and no compensation event arises from such instruction.",
     "high","variation","true","UK","NEC4","Removal of compensation event for stop/start instructions; contractor bears cost of downtime."),
    ("The Contractor shall submit a programme to the Project Manager within 21 days of Contract Date; failure to submit an accepted programme means that 25% of all sums otherwise due to the Contractor shall be retained.",
     "high","delay","true","UK","NEC4","Punitive 25% payment withholding for programme failure; unusually aggressive sanction."),
    ("The Contractor shall not be entitled to a compensation event where the Contractor failed to give early warning of the matter which caused the event.",
     "high","delay","true","UK","NEC4","Loss of CE entitlement for failure to give early warning; strict application has harsh financial effect."),
    ("The Employer may instruct the Contractor to submit a revised quotation if the Project Manager considers the original quotation unreasonable, and the Project Manager's assessment shall be final.",
     "high","variation","true","UK","NEC4","PM's assessment of CE is final; removes contractor's ability to challenge valuation."),
    ("All risk of ground conditions at the Site remains with the Contractor regardless of the Site Information provided; no compensation event arises from physical conditions.",
     "high","site_conditions","true","UK","NEC4","Full ground risk on contractor even where site information proves inaccurate; contrary to Z60.1 CE."),
    ("The Contractor shall not be entitled to a compensation event for delay caused by any action or inaction of a subcontractor or supplier.",
     "high","delay","true","UK","NEC4","Sub-contractor delay risk entirely on contractor with no pass-through to employer."),
    ("The Project Manager may assess a compensation event at any time and the Contractor shall have no right to submit its own quotation.",
     "high","variation","true","UK","NEC4","Removal of contractor's right to quote for CEs; PM-only assessment is contrary to NEC4 spirit."),
    ("The Contractor shall be liable for delay damages at the rate stated in Contract Data Part 1 for every day of delay, with no cap on total liability.",
     "high","delay","true","UK","NEC4","Uncapped daily delay damages; creates unlimited financial exposure for contractor."),
    ("The Contractor accepts the risk of legal changes to the law of any country applicable to the Contractor's work and no compensation event arises from change in law.",
     "high","regulatory","true","UK","NEC4","Change-in-law risk transferred to contractor; contrary to standard NEC4 CE 60.1(18)."),
    ("The Employer may terminate the Contractor's employment for any reason and the Contractor shall be entitled only to an amount equal to the Defined Cost incurred to date less a 10% reduction.",
     "high","termination","true","UK","NEC4","Termination for convenience with punitive 10% reduction; contractor has no entitlement to profit or pipeline contribution."),
    ("Where the Contractor fails to notify a compensation event within 8 weeks, the Contractor loses entitlement to any time or cost adjustment arising from that event.",
     "high","delay","true","UK","NEC4","8-week notification bar is strict; permanent loss of entitlement is a significant risk."),
    ("The Employer may withhold payment of any amount due pending resolution of any dispute, without serving a pay less notice.",
     "high","payment","true","UK","NEC4","Payment withholding without pay less notice undermines NEC4's payment transparency mechanisms."),
    ("The Contractor shall correct all Defects within 7 days of notification regardless of their nature or complexity, failing which the Employer may employ others and recover the cost plus 50%.",
     "high","warranty","true","UK","NEC4","Impossibly short defect correction window with punitive 50% premium recovery."),
    ("The Contractor accepts all risk for errors in the Scope or Works Information provided by the Employer and shall not be entitled to any adjustment of the Prices or Completion Date.",
     "high","variation","true","UK","NEC4","Employer's scope errors become contractor's risk; contrary to CE 60.1(1)."),
]

NEC4_MEDIUM = [
    ("The Contractor is to give an early warning of any matter which could increase the total Defined Cost, delay Completion or impair performance of the works in use.",
     "medium","delay","false","UK","NEC4","EW obligation is core NEC4 requirement; failure to warn may reduce CE entitlement."),
    ("The Project Manager may instruct a change to the Scope and the change is a compensation event.",
     "medium","variation","false","UK","NEC4","Standard CE for scope change; balanced provision."),
    ("The Contractor is to assess the compensation event using the Shorter Schedule of Cost Components where the work has not been done.",
     "medium","variation","false","UK","NEC4","SSCC use for prospective CEs; requires forecast which introduces uncertainty."),
    ("If the Project Manager does not reply to a communication from the Contractor within the period for reply, the Contractor may notify the Project Manager that the period has expired.",
     "medium","delay","false","UK","NEC4","Inactivity CE mechanism; protects contractor from PM delay in responding."),
    ("The Contractor provides forecasts of the total Defined Cost at intervals stated in the Contract Data.",
     "medium","payment","false","UK","NEC4","Cost forecasting obligation; administrative burden but provides transparency."),
    ("The Project Manager may give an instruction requiring a Defect to be corrected within a shorter defect correction period than the one stated in the Contract Data.",
     "medium","warranty","true","UK","NEC4","PM can shorten defect correction period; some contractor risk but subject to reasonableness."),
    ("The Contractor notifies the Project Manager of each compensation event within 8 weeks of becoming aware that the event has happened.",
     "medium","delay","false","UK","NEC4","CE notification deadline; manageable but requires diligent programme management."),
    ("The Contractor is to prepare the first programme to show the information stated in this Contract within the period stated in the Contract Data.",
     "medium","delay","false","UK","NEC4","Programme submission obligation; standard NEC4 requirement."),
    ("The Contractor is to submit revised programmes whenever the Project Manager instructs, or when the Contractor chooses.",
     "medium","delay","false","UK","NEC4","Programme updating obligation; reasonable and standard."),
    ("The Employer provides the Site and the means of access to and from the Site to the Contractor on time.",
     "medium","site_conditions","false","UK","NEC4","Employer's access obligation; breach is a CE."),
    ("The Contractor provides services and facilities listed in the Scope at the times and for the periods stated.",
     "medium","administrative","false","UK","NEC4","Service provision obligation; scope-dependent risk."),
    ("A compensation event is not notified if the Employer or the Contractor did not give an early warning of the event when they could have done so.",
     "medium","delay","true","UK","NEC4","Mutual early warning obligation; applies to both parties but in practice limits contractor CEs."),
    ("The Project Manager may assess a compensation event if the Contractor has not submitted a required quotation within the time allowed.",
     "medium","variation","true","UK","NEC4","PM assessment on contractor delay; some risk but provides programme certainty."),
    ("The Contractor is to provide the Project Manager with information which the Project Manager needs in order to issue a certificate.",
     "medium","administrative","false","UK","NEC4","Information provision obligation; standard."),
    ("The Contractor repays to the Employer the amount of any overpayment on the next payment date.",
     "medium","payment","false","UK","NEC4","Overpayment recovery; balanced and expected."),
    ("An amount due is calculated at each assessment date by the Project Manager and Contractor jointly, or by the Project Manager alone if the Contractor does not attend.",
     "medium","payment","false","UK","NEC4","Joint assessment preferred; PM can proceed alone if contractor absent."),
    ("The Contractor is to submit the first assessment of the amount due no later than the first assessment date.",
     "medium","payment","false","UK","NEC4","Application submission obligation; standard NEC4."),
    ("The Project Manager may give an instruction to stop or not start any work for safety or other urgent reason.",
     "medium","variation","false","UK","NEC4","Stop work instruction with underlying CE entitlement for contractor."),
    ("The Contractor is to obtain the Project Manager's approval before starting the design of each part of the works.",
     "medium","variation","false","UK","NEC4","Design approval obligation; standard for ECC Option A with contractor design."),
    ("The Contractor is to refer a dispute to the Dispute Avoidance Board within 4 weeks of becoming aware of the dispute.",
     "medium","dispute","false","UK","NEC4","DAB referral timeframe; standard NEC4 W3 procedure."),
]

NEC4_LOW = [
    ("The Project Manager gives access to the Site to the Contractor on the access date stated in Contract Data Part 1.",
     "low","administrative","false","UK","NEC4","Standard access provision; employer obligation."),
    ("The Employer and the Contractor shall act in a spirit of mutual trust and co-operation.",
     "low","administrative","false","UK","NEC4","Core NEC4 collaboration obligation; aspirational but fundamental."),
    ("The Project Manager is to act as stated in this Contract and in a spirit of mutual trust and co-operation.",
     "low","administrative","false","UK","NEC4","PM duty of mutual trust; mirrors contractor obligation."),
    ("The Contractor Provides the Works in accordance with the Scope and this Contract.",
     "low","administrative","false","UK","NEC4","Fundamental contractor obligation; standard."),
    ("The Contractor is to provide the Project Manager with a first programme showing the information required by this Contract.",
     "low","delay","false","UK","NEC4","Programme provision obligation; standard."),
    ("The Project Manager certifies a payment in the amount due within one week of each assessment date.",
     "low","payment","false","UK","NEC4","Payment certification timeline; standard NEC4."),
    ("The Employer pays the amount due within 3 weeks of each assessment date.",
     "low","payment","false","UK","NEC4","Standard NEC4 payment period; clear employer obligation."),
    ("The Contractor corrects notified Defects before the defect correction date.",
     "low","warranty","false","UK","NEC4","Standard defect correction obligation; reasonable timeframe."),
    ("The Contractor's share is calculated at the end of the project as stated in the Contract.",
     "low","payment","false","UK","NEC4","Pain/gain share clause; incentivises contractor cost efficiency."),
    ("The Contractor and Project Manager attend each early warning meeting.",
     "low","administrative","false","UK","NEC4","Risk register and EW meeting attendance; collaborative and standard."),
    ("The risk register is issued to the Contractor at the starting date.",
     "low","administrative","false","UK","NEC4","Risk register provision; promotes transparent risk management."),
    ("The Project Manager may change the Scope to accept a Defect.",
     "low","warranty","false","UK","NEC4","Scope change to accept defect with compensation adjustment; balanced."),
    ("A Defect is a part of the works which is not in accordance with the Scope.",
     "low","warranty","false","UK","NEC4","Standard definition of defect."),
    ("The Completion Date is the date in the Accepted Programme for Completion, adjusted for compensation events.",
     "low","delay","false","UK","NEC4","Completion Date definition; programme-linked."),
    ("The Project Manager issues a Completion Certificate when the Contractor has done all the work necessary to complete the works.",
     "low","delay","false","UK","NEC4","Completion certification; standard milestone."),
    ("The Contractor obtains required approvals from Others and notifies the Project Manager before starting work which needs such approval.",
     "low","regulatory","false","UK","NEC4","Third party approval obligation; standard."),
    ("The Project Manager notifies the Contractor of each Defect as soon as he finds it.",
     "low","warranty","false","UK","NEC4","PM's notification obligation; balanced duty."),
    ("Either Party may terminate the Contractor's obligation to Provide the Works if the other Party has committed a reason stated in this Contract.",
     "low","termination","false","UK","NEC4","Standard mutual termination for cause; balanced."),
    ("The Client may terminate the Contractor's obligation to Provide the Works at any time.",
     "low","termination","true","UK","NEC4","Termination for convenience right; contractor receives defined cost plus profit entitlement under NEC4."),
    ("The Contractor maintains the Site as free from rubbish and the Contractor's equipment as the Project Manager instructs.",
     "low","site_conditions","false","UK","NEC4","Site tidiness obligation; standard."),
]

NEC4_OPPORTUNITY = [
    ("If the Project Manager does not assess a compensation event within the time allowed, the Contractor's quotation is treated as accepted.",
     "opportunity","variation","true","UK","NEC4","Deemed acceptance of contractor's CE quotation on PM inaction; contractor-favourable mechanism."),
    ("The Contractor is entitled to a compensation event where the Employer or Others do not work within the times shown in the Accepted Programme.",
     "opportunity","delay","false","UK","NEC4","CE for Others' delay; contractor protected where employer-managed parties cause delay."),
    ("Where the Project Manager gives an instruction changing the Scope after the Contract Date, all additional Defined Cost and time is recoverable as a compensation event.",
     "opportunity","variation","false","UK","NEC4","Full cost and time recovery on scope change CE; standard NEC4 protection."),
    ("The Contractor is entitled to a compensation event where a physical condition encountered is one which an experienced contractor would have judged at the Contract Date to have a small chance of occurring.",
     "opportunity","site_conditions","false","UK","NEC4","Unforeseeable ground conditions CE; standard NEC4 60.1(12) protection."),
    ("The Contractor's share of savings achieved below the Target Cost shall be calculated at 50% of the underspend.",
     "opportunity","payment","false","UK","NEC4","50% gainshare on Option C target; significant upside for efficient contractor."),
    ("Where the Employer fails to provide something they are to provide by the date stated, the Contractor is entitled to a compensation event for delay and additional cost.",
     "opportunity","delay","false","UK","NEC4","Employer supply chain risk passed back to employer; contractor protected for late employer-furnished items."),
    ("The Contractor is entitled to a compensation event where the Project Manager gives an instruction to stop work, and the stop lasts more than 13 weeks, and no further instruction is given.",
     "opportunity","delay","false","UK","NEC4","Prolonged stop-work triggers CE; protects contractor's standing costs."),
    ("The Contractor retains ownership of its Equipment and Plant brought onto Site until the Contract is terminated or the items are removed.",
     "opportunity","payment","true","UK","NEC4","Retention of title for contractor's equipment; protects assets on employer insolvency."),
    ("The Contractor is entitled to a prevention event compensation where the event stops the Contractor completing the works and neither party could have prevented it.",
     "opportunity","force_majeure","false","UK","NEC4","Prevention event CE; contractor recovers time and cost for unforeseeable force majeure events."),
    ("Where the Employer terminates for convenience, the Contractor is entitled to Defined Cost of work done, profit on work done, and a fee for breaking subcontracts.",
     "opportunity","termination","false","UK","NEC4","Termination for convenience with full cost recovery including profit; standard NEC4 R21 entitlement."),
]

NEC4_NEUTRAL = [
    ("CORE CLAUSES","neutral","administrative","false","UK","NEC4","NEC4 structural heading."),
    ("SECTION 1 – GENERAL","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 2 – THE CONTRACTOR'S MAIN RESPONSIBILITIES","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 3 – TIME","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 4 – TESTING AND DEFECTS","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 5 – PAYMENT","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 6 – COMPENSATION EVENTS","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 7 – TITLE","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 8 – RISKS AND INSURANCE","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("SECTION 9 – TERMINATION","neutral","administrative","false","UK","NEC4","NEC4 section heading."),
    ("'Works Information' means information which specifies and describes the works or states any constraint on how the Contractor Provides the Works.",
     "neutral","administrative","false","UK","NEC4","Standard NEC4 definition."),
    ("'Defined Cost' means the amounts calculated by applying the Schedule of Cost Components or Shorter Schedule of Cost Components.",
     "neutral","administrative","false","UK","NEC4","Standard NEC4 cost definition."),
    ("'Compensation Event' means an event which entitles the Contractor to changes to the Prices and Completion Date.",
     "neutral","administrative","false","UK","NEC4","Standard NEC4 compensation event definition."),
    ("'The Fee' means the tendered fee percentage applied to Defined Cost.",
     "neutral","administrative","false","UK","NEC4","Standard NEC4 fee definition."),
    ("'Key Date' means the date by which the Contractor is to meet a Condition stated in the Contract Data.",
     "neutral","administrative","false","UK","NEC4","Standard NEC4 Key Date definition."),
    ("CONTRACT DATA PART 1 – DATA PROVIDED BY THE EMPLOYER","neutral","administrative","false","UK","NEC4","Standard NEC4 document heading."),
    ("CONTRACT DATA PART 2 – DATA PROVIDED BY THE CONTRACTOR","neutral","administrative","false","UK","NEC4","Standard NEC4 document heading."),
    ("This contract is a NEC4 Engineering and Construction Contract.",
     "neutral","administrative","false","UK","NEC4","Contract identification clause."),
    ("The language of this contract is English.",
     "neutral","administrative","false","UK","NEC4","Language clause; standard."),
    ("The law of the contract is the law of England and Wales.",
     "neutral","administrative","false","UK","NEC4","Governing law; standard for UK NEC4 contract."),
]

BESPOKE_ZW_HIGH = [
    ("The Contractor shall be liable for liquidated damages at the rate of USD 5,000 per day for every day of delay beyond the Completion Date, without any limit on the aggregate amount recoverable.",
     "high","delay","true","ZW","bespoke","Uncapped daily LADs in USD; creates severe and uninsurable financial exposure for Zimbabwean contractors."),
    ("The Employer may withhold any amount due to the Contractor pending settlement of any claim by the Employer, whether or not such claim is disputed or related to the current Works.",
     "high","payment","true","ZW","bespoke","Unrestricted withholding right; allows employer to use unrelated claims to delay payment indefinitely."),
    ("All payments under this Contract shall be made in United States Dollars; any payment made in RTGS or ZiG currency shall not discharge the Contractor's payment obligation.",
     "high","payment","true","ZW","bespoke","USD-only payment in reverse; in context where contractor is employer, this shifts forex risk onto subcontractor."),
    ("The Contractor shall provide a retention bond and a performance bond each equal to 10% of the Contract Price, totalling 20% of the Contract Price, within 7 days of award.",
     "high","administrative","true","ZW","bespoke","Excessive bonding requirement of 20% combined; significant liquidity burden on contractor."),
    ("The Employer may terminate this Contract at any time without cause or notice, and the Contractor shall have no claim for loss of profit, overhead recovery or any other damages arising from such termination.",
     "high","termination","true","ZW","bespoke","At-will termination without compensation; contractor loses all anticipated returns on investment."),
    ("The Contractor warrants that it has independently investigated all site conditions, surrounding infrastructure and sub-surface geology, and accepts all risk therefrom without any entitlement to additional payment.",
     "high","site_conditions","true","ZW","bespoke","Full unforeseeable ground risk on contractor; removes employer's implied obligation to disclose site information."),
    ("In the event of any dispute, the Employer's decision shall be final and binding; the Contractor shall continue to perform the Works pending any subsequent arbitration.",
     "high","dispute","true","ZW","bespoke","Employer as sole arbiter of disputes; no independent decision-making; contractor must perform under adverse decisions."),
    ("The Contractor shall indemnify the Employer against all costs, claims and expenses arising from the Contractor's presence on site, including claims by third parties, whether or not caused by the Contractor's negligence.",
     "high","indemnity","true","ZW","bespoke","Negligence-free indemnity; contractor becomes insurer for all site-related third party claims."),
    ("All Contractor's equipment, materials and temporary works brought onto Site shall be deemed to be the property of the Employer for the duration of the Contract and shall not be removed without Employer's written consent.",
     "high","payment","true","ZW","bespoke","Deemed vesting of contractor's property; exposes contractor to loss if employer becomes insolvent or hostile."),
    ("Escalation shall not apply to any element of the Contract Sum; the Contractor accepts all risks of price escalation in materials, labour and equipment for the full duration of the Contract.",
     "high","payment","true","ZW","bespoke","Full escalation risk on contractor in Zimbabwe's volatile inflation environment; commercially dangerous on long contracts."),
    ("The Contractor shall not be entitled to any extension of time or additional payment for delays caused by shortage of materials, foreign currency unavailability, or import permit delays.",
     "high","delay","true","ZW","bespoke","Risk of Zimbabwe-specific disruptions (forex, import permits) fully on contractor; foreseeable sovereign risk excluded."),
    ("Any amounts due to the Contractor may be set off against any claim the Employer may have against the Contractor under any other contract between the parties.",
     "high","payment","true","ZW","bespoke","Cross-contract set-off right; allows employer to use disputes on other contracts to withhold current payments."),
    ("The Employer shall have the right to vary the scope of Works by up to 50% without any adjustment to the unit rates or time for completion.",
     "high","variation","true","ZW","bespoke","50% scope variation without rate adjustment; contractor's preliminaries and profit margin severely eroded on major omissions."),
    ("The Contractor shall be responsible for obtaining all statutory approvals, permits and licences required for the Works at its own cost, and delays arising from the permitting process shall not entitle the Contractor to any extension of time.",
     "high","regulatory","true","ZW","bespoke","Contractor bears permitting risk in a jurisdiction with unpredictable regulatory timelines."),
    ("Any payment certified by the Quantity Surveyor shall be subject to the Employer's approval before becoming due; the Employer may reduce the certified amount without limitation.",
     "high","payment","true","ZW","bespoke","Employer veto over QS certification; undermines independence of certification process."),
    ("The Contractor shall complete the Works within the time stated even if access, materials or instructions are delayed; no extension of time shall be granted for any cause whatsoever.",
     "high","delay","true","ZW","bespoke","Absolute completion obligation with no EOT; imposes strict liability for delays not within contractor's control."),
    ("The Sub-Contractor shall not be entitled to payment for variations unless a signed Variation Order is produced prior to commencing the varied work; verbal instructions shall not create payment entitlement.",
     "high","variation","true","ZW","bespoke","Pre-variation-order condition precedent; practical impossibility on live construction sites denies contractors legitimate claims."),
    ("The Employer may deduct the cost of rectifying any defect from amounts otherwise due to the Contractor without first notifying the Contractor or giving it an opportunity to rectify.",
     "high","warranty","true","ZW","bespoke","Deduction without notice or opportunity to cure; denies contractor natural justice."),
    ("All disputes shall be resolved by arbitration in terms of the Arbitration Act [Chapter 7:15] of Zimbabwe; the arbitrator shall be appointed solely by the Employer.",
     "high","dispute","true","ZW","bespoke","Employer-appointed arbitrator lacks independence; contrary to fair arbitration principles."),
    ("The Contractor shall bear the cost of all power, water, telecommunications and site services throughout the Contract Period; no allowance has been made in the Contract Sum.",
     "high","site_conditions","true","ZW","bespoke","Undisclosed service costs to be borne by contractor; creates hidden financial risk."),
    ("The Contractor shall maintain all statutory insurances in Zimbabwe including Workers' Compensation, NSSA contributions and third party public liability at its own cost without any reimbursement from the Employer.",
     "medium","regulatory","false","ZW","bespoke","Standard statutory insurance obligations in Zimbabwe; contractor bears cost but this is normal."),
    ("The Contractor shall comply with all ZESA regulations regarding electrical installations and shall obtain ZESA certification before energising any electrical systems.",
     "low","regulatory","false","ZW","bespoke","Standard regulatory compliance obligation; Zimbabwe ZESA requirement."),
    ("The Contractor shall pay all employees a minimum wage not less than the applicable ZITS/ZCEA minimum wage for the construction sector.",
     "low","regulatory","false","ZW","bespoke","Labour law compliance; Zimbabwe Construction Industry Federation wage requirement."),
    ("The Contractor shall register the project with the Zimbabwe Revenue Authority and comply with all ZIMRA withholding tax obligations.",
     "low","regulatory","false","ZW","bespoke","Tax compliance obligation; standard for Zimbabwe construction projects."),
    ("The Employer shall provide the Contractor with access to borehole water on site at no charge for construction use.",
     "low","site_conditions","false","ZW","bespoke","Employer-provided site water; reduces contractor's site overhead."),
]

BESPOKE_ZW_MEDIUM = [
    ("Payment applications shall be submitted by the Contractor on the 25th of each month; the Employer's Quantity Surveyor shall certify within 14 days and payment shall be made within 30 days of certification.",
     "medium","payment","false","ZW","bespoke","Payment cycle of approximately 44 days; acceptable but on the longer side for Zimbabwe market."),
    ("The Contractor shall maintain a 10% retention throughout the Works, reducing to 5% on Practical Completion; the balance shall be released at the end of the 12-month Defects Liability Period.",
     "medium","payment","false","ZW","bespoke","Standard retention regime for Zimbabwe; rates are at market norm."),
    ("All variations must be supported by a Variation Order signed by the Employer's Representative before work commences, except in cases of urgency where verbal instruction may be confirmed in writing within 48 hours.",
     "medium","variation","false","ZW","bespoke","VO requirement with urgency exception; balanced but requires contractor diligence."),
    ("The Contractor shall provide a performance guarantee of 10% of the Contract Sum from an acceptable financial institution within 14 days of Contract execution.",
     "medium","administrative","false","ZW","bespoke","10% performance guarantee; market norm in Zimbabwe but creates liquidity demand."),
    ("Disputes shall be referred to a Dispute Adjudication Board constituted in terms of FIDIC where the Contract is administered under FIDIC, or to the AFCCA in other cases.",
     "medium","dispute","false","ZW","bespoke","Tiered dispute resolution; appropriate for Zimbabwe construction disputes."),
    ("The Contractor shall submit a construction programme in bar chart form within 21 days of the Commencement Date and update it monthly.",
     "medium","delay","false","ZW","bespoke","Programme obligation; standard practice in Zimbabwe."),
    ("The Employer may grant an extension of time for delays caused by force majeure events including acts of God, floods, civil unrest, government action or unavailability of foreign currency.",
     "medium","force_majeure","false","ZW","bespoke","Force majeure definition includes Zimbabwe-specific risks (forex, civil unrest); balanced provision."),
    ("The Contractor shall be responsible for paying all import duties and clearing charges on materials brought into Zimbabwe for the Works, unless specifically stated otherwise in the Contract Data.",
     "medium","payment","true","ZW","bespoke","Import duty risk on contractor; significant exposure given Zimbabwe's import tariff environment."),
    ("The Contractor shall comply with all local authority requirements, including those of the City of Harare/Bulawayo City Council, for excavation in public areas.",
     "medium","regulatory","false","ZW","bespoke","Local authority compliance obligation; standard but requires advance planning."),
    ("The Contractor shall maintain and operate a complaints handling procedure for affected community members throughout the Contract Period.",
     "medium","regulatory","false","ZW","bespoke","Community engagement obligation; increasingly common on Zimbabwe infrastructure contracts."),
    ("Payment of the Contract Sum shall be 50% in United States Dollars and 50% in Zimbabwe Gold (ZiG) at the official exchange rate published by RBZ on the payment date.",
     "medium","payment","false","ZW","bespoke","Dual-currency payment mechanism; reflects Zimbabwe's multi-currency environment; ZiG portion carries exchange rate risk."),
    ("The Contractor shall submit an Environmental Management Plan in accordance with EMA regulations within 30 days of Contract Date.",
     "medium","regulatory","false","ZW","bespoke","EMA compliance requirement; mandatory for infrastructure projects in Zimbabwe."),
    ("The Employer shall provide the Contractor with a Letter of Credit from an approved bank as security for payment of amounts exceeding USD 100,000.",
     "medium","payment","false","ZW","bespoke","Payment security mechanism; protects contractor against employer insolvency on large contracts."),
    ("The Contractor shall employ a minimum of 70% local Zimbabwean labour in the execution of the Works.",
     "medium","regulatory","false","ZW","bespoke","Local content labour requirement; common condition on government-funded Zimbabwe projects."),
    ("The Contractor shall not carry out any blasting operations without prior written approval from SADC Explosives Board and notification to the Employer's Representative.",
     "medium","regulatory","false","ZW","bespoke","Blasting approval requirement; safety-critical and regulatory."),
    ("The Employer shall nominate and pay directly any nominated subcontractors; the Contractor shall be responsible for coordinating nominated subcontractors but not for their defaults.",
     "medium","variation","false","ZW","bespoke","Nominated subcontractor mechanism; limits contractor's liability for employer-selected specialists."),
    ("The Contractor shall submit a cashflow forecast with each payment application to assist the Employer with funding arrangements.",
     "medium","payment","false","ZW","bespoke","Cashflow forecasting obligation; transparent but creates administrative burden."),
    ("All cement, steel, bitumen and other principal materials shall be sourced from Zimbabwean manufacturers where available and comparable in quality and price.",
     "medium","variation","false","ZW","bespoke","Local sourcing preference; may restrict contractor's supply chain and increase material risk."),
    ("The Contractor shall implement and maintain an HIV/AIDS awareness programme for all site workers throughout the duration of the Works.",
     "medium","regulatory","false","ZW","bespoke","HIV/AIDS programme obligation; standard on large Zimbabwe infrastructure contracts."),
    ("Provisional sums included in the Contract Bills shall only be expended on the written instruction of the Employer's Representative.",
     "medium","payment","false","ZW","bespoke","Provisional sum control mechanism; standard QS practice."),
]

BESPOKE_ZW_LOW = [
    ("The Commencement Date shall be the date stated in the Letter of Acceptance, and the Contractor shall commence Works within 7 days thereof.",
     "low","administrative","false","ZW","bespoke","Standard commencement obligation."),
    ("The Contractor shall keep a daily site diary recording weather conditions, labour strength, materials received and work carried out.",
     "low","administrative","false","ZW","bespoke","Site record-keeping obligation; standard practice."),
    ("The Employer's Representative shall have authority to issue instructions on behalf of the Employer in all matters relating to the administration of this Contract.",
     "low","administrative","false","ZW","bespoke","Defines employer's representative authority; standard."),
    ("The Contractor shall erect and maintain a Project Sign Board in accordance with the Employer's specifications within 7 days of Commencement.",
     "low","administrative","false","ZW","bespoke","Signage obligation; administrative, low risk."),
    ("The Works shall be carried out in accordance with the drawings, specifications and Bill of Quantities forming part of this Contract.",
     "low","administrative","false","ZW","bespoke","Fundamental obligation to comply with contract documents; standard."),
    ("The Employer shall provide survey benchmarks and reference points for the Contractor's use in setting out the Works.",
     "low","administrative","false","ZW","bespoke","Employer's setting-out support obligation; standard."),
    ("The Contractor shall be responsible for setting out the Works from the reference points provided and shall verify all dimensions before commencing construction.",
     "low","administrative","false","ZW","bespoke","Contractor's setting-out responsibility; standard obligation."),
    ("The Contractor shall maintain public roads used by construction traffic in a clean and tidy condition at all times.",
     "low","regulatory","false","ZW","bespoke","Road maintenance obligation; standard and reasonable."),
    ("The Employer shall pay the Contract Price in the currency or currencies stated in the Contract Data.",
     "low","payment","false","ZW","bespoke","Currency of payment clause; basic obligation."),
    ("Either party shall give 14 days' written notice of any change in address for service of notices.",
     "low","administrative","false","ZW","bespoke","Notice address update obligation; administrative."),
    ("The Contract shall be governed by the law of Zimbabwe and any disputes shall be subject to the jurisdiction of Zimbabwean courts.",
     "low","administrative","false","ZW","bespoke","Governing law and jurisdiction; standard for Zimbabwe contracts."),
    ("The Contractor shall ensure that all waste generated during the Works is disposed of in accordance with EMA regulations.",
     "low","regulatory","false","ZW","bespoke","Waste disposal obligation; EMA compliance standard."),
    ("The Contractor shall provide adequate sanitary facilities for all site workers throughout the Contract Period.",
     "low","site_conditions","false","ZW","bespoke","Site welfare obligation; standard and required by NSSA."),
    ("The Employer's Representative may attend any site operations, tests or inspections at any time without prior notice.",
     "low","administrative","false","ZW","bespoke","Access right for employer's representative; standard."),
    ("The Contractor shall submit as-built drawings within 28 days of Practical Completion.",
     "low","administrative","false","ZW","bespoke","As-built record submission obligation; standard completion deliverable."),
    ("The Contractor shall provide training to the Employer's maintenance staff on the operation of installed plant and equipment.",
     "low","administrative","false","ZW","bespoke","Training obligation; standard on M&E and infrastructure contracts."),
    ("The Contractor shall submit a final account within 90 days of Practical Completion.",
     "low","administrative","false","ZW","bespoke","Final account submission obligation; standard."),
    ("Certificates issued under this Contract shall not be taken as evidence that the Works have been completed in accordance with the Contract.",
     "low","administrative","false","ZW","bespoke","Standard certification disclaimer."),
    ("The Contractor shall comply with the Employer's Health, Safety and Environment policy as issued and updated from time to time.",
     "low","regulatory","false","ZW","bespoke","HSE policy compliance obligation; standard."),
    ("The Contractor shall permit the Auditor General or any authorised representative to inspect all financial records relating to this Contract.",
     "low","administrative","false","ZW","bespoke","Government audit access right; standard on public sector Zimbabwe contracts."),
]

BESPOKE_ZW_OPPORTUNITY = [
    ("Where the Employer fails to certify payment within the prescribed period, the Contractor shall be entitled to suspend the Works after giving 7 days' written notice.",
     "opportunity","payment","false","ZW","bespoke","Suspension right on late certification; strengthens contractor's cash flow protection in Zimbabwe's difficult payment environment."),
    ("The Contractor shall be entitled to an extension of time and additional cost for delays caused by unavailability of foreign currency for imported materials, provided such unavailability is documented by a bank.",
     "opportunity","force_majeure","false","ZW","bespoke","Forex-induced delay recognised as relief event; critical protection in Zimbabwe's USD-constrained environment."),
    ("Where the Contract Sum is denominated in USD, all payments shall be made in USD or at the parallel market rate, whichever is more favourable to the Contractor.",
     "opportunity","payment","true","ZW","bespoke","Parallel market rate protection; significant financial benefit for contractor in multi-currency Zimbabwe environment."),
    ("The Employer shall pay the Contractor a mobilisation advance of 15% of the Contract Sum, secured by an advance payment guarantee, within 30 days of contract execution.",
     "opportunity","payment","false","ZW","bespoke","Mobilisation advance at 15%; strong cash flow support for contractor on project start."),
    ("Price escalation shall be calculated monthly using the CPIH index published by ZIMSTAT; all increases shall be paid in the same currency as the Contract Sum.",
     "opportunity","payment","false","ZW","bespoke","Escalation clause with ZIMSTAT index; full price protection for contractor in inflationary environment."),
    ("Where the Employer issues an omission instruction, the Contractor shall be entitled to recover its preliminaries and time-related costs attributable to the omitted work.",
     "opportunity","variation","true","ZW","bespoke","Preliminaries recovery on omissions; protects contractor's fixed cost recovery on scope reductions."),
    ("The Contractor shall be entitled to a daywork rate premium of 35% on direct cost for all instructed dayworks, together with a percentage addition for profit and overhead.",
     "opportunity","variation","false","ZW","bespoke","Above-market daywork premium; improves contractor's margin on time-and-materials work."),
    ("On termination of the Contract by the Employer for convenience, the Contractor shall be entitled to the full value of work executed, loss of profit on remaining work, and demobilisation costs.",
     "opportunity","termination","false","ZW","bespoke","Full termination-for-convenience entitlement; contractor recovers profit on unexecuted work."),
    ("Where the Employer fails to take possession of the completed Works within 14 days of Practical Completion, the Contractor shall be entitled to storage charges at a rate of 0.5% of the Contract Sum per week.",
     "opportunity","delay","true","ZW","bespoke","Storage charges on employer's failure to take possession; monetises employer-caused delay post-completion."),
    ("The Contractor shall retain the right to remove from Site any equipment, materials and temporary works paid for by the Contractor at any time.",
     "opportunity","payment","false","ZW","bespoke","Retention of title and removal right; protects contractor's assets against employer default."),
    ("The Contractor shall be entitled to payment of interest at a rate of 5% above the RBZ overnight lending rate on all overdue amounts calculated from the due date.",
     "opportunity","payment","false","ZW","bespoke","Interest on late payment tied to RBZ rate; commercially reasonable and common on Zimbabwe contracts."),
    ("Where a nominated subcontractor fails to perform, the Employer shall bear the resulting delay costs and shall grant an extension of time to the Contractor.",
     "opportunity","delay","false","ZW","bespoke","Employer's risk for nominated subcontractor failure; contractor protected from third-party defaults imposed by employer."),
]

BESPOKE_ZW_NEUTRAL = [
    ("AGREEMENT","neutral","administrative","false","ZW","bespoke","Contract heading."),
    ("GENERAL CONDITIONS OF CONTRACT","neutral","administrative","false","ZW","bespoke","Document heading."),
    ("SPECIAL CONDITIONS OF CONTRACT","neutral","administrative","false","ZW","bespoke","Document heading; modifications to general conditions."),
    ("SCHEDULE OF RATES AND QUANTITIES","neutral","administrative","false","ZW","bespoke","Pricing document heading."),
    ("SECTION 1: PARTIES TO THE CONTRACT","neutral","administrative","false","ZW","bespoke","Contract parties section."),
    ("SECTION 2: DEFINITIONS","neutral","administrative","false","ZW","bespoke","Definitions section heading."),
    ("SECTION 3: SCOPE OF WORKS","neutral","administrative","false","ZW","bespoke","Scope section heading."),
    ("SECTION 4: CONTRACT PRICE AND PAYMENT","neutral","administrative","false","ZW","bespoke","Payment section heading."),
    ("SECTION 5: PROGRAMME AND COMPLETION","neutral","administrative","false","ZW","bespoke","Programme section heading."),
    ("SECTION 6: VARIATIONS","neutral","administrative","false","ZW","bespoke","Variations section heading."),
    ("SECTION 7: INSURANCE","neutral","administrative","false","ZW","bespoke","Insurance section heading."),
    ("SECTION 8: FORCE MAJEURE","neutral","administrative","false","ZW","bespoke","Force majeure section heading."),
    ("SECTION 9: DISPUTE RESOLUTION","neutral","administrative","false","ZW","bespoke","Dispute resolution section heading."),
    ("SECTION 10: TERMINATION","neutral","administrative","false","ZW","bespoke","Termination section heading."),
    ("ANNEXURE A: CONTRACT DATA","neutral","administrative","false","ZW","bespoke","Contract data annexure heading."),
    ("ANNEXURE B: CONSTRUCTION PROGRAMME","neutral","administrative","false","ZW","bespoke","Programme annexure heading."),
    ("ANNEXURE C: PERFORMANCE BOND FORM","neutral","administrative","false","ZW","bespoke","Performance bond form heading."),
    ("'Commencement Date' means the date stated in the Letter of Acceptance from which the Contract Period is calculated.",
     "neutral","administrative","false","ZW","bespoke","Standard definition; administrative."),
    ("'Contract Price' means the sum stated in the Letter of Acceptance, subject to adjustment in accordance with this Contract.",
     "neutral","administrative","false","ZW","bespoke","Standard contract price definition."),
    ("'Practical Completion' means the stage at which the Works are sufficiently complete to be used for their intended purpose, as certified by the Employer's Representative.",
     "neutral","administrative","false","ZW","bespoke","Standard practical completion definition for Zimbabwe contracts."),
    ("'Defects Liability Period' means the period of 12 months following Practical Completion during which the Contractor is liable to rectify defects.",
     "neutral","administrative","false","ZW","bespoke","Standard DLP definition."),
    ("'Employer's Representative' means the person appointed by the Employer to administer the Contract on its behalf.",
     "neutral","administrative","false","ZW","bespoke","Standard ER definition."),
    ("IN WITNESS WHEREOF the parties have signed this Contract on the date first written above.",
     "neutral","administrative","false","ZW","bespoke","Execution clause."),
    ("SIGNED for and on behalf of THE EMPLOYER by a duly authorised representative:",
     "neutral","administrative","false","ZW","bespoke","Execution signature block."),
    ("SIGNED for and on behalf of THE CONTRACTOR by a duly authorised representative:",
     "neutral","administrative","false","ZW","bespoke","Execution signature block."),
]

FIDIC_HIGH = [
    ("The Contractor shall give notice to the Engineer within 28 days after the Contractor became aware, or should have become aware, of the event or circumstance giving rise to the claim; failing which the Contractor shall be entitled to no additional payment.",
     "high","delay","true","ZW","FIDIC","FIDIC 2017 Red Book Clause 20.2.1 time bar; strict 28-day notice condition precedent with permanent loss of entitlement."),
    ("The Employer may terminate the Contract for convenience by giving 28 days' notice; the Contractor shall be entitled only to Cost incurred plus 3% of the Cost as profit.",
     "high","termination","true","ZW","FIDIC","Termination for convenience with limited profit entitlement; 3% profit capped regardless of anticipated margin."),
    ("The Contractor shall indemnify the Employer against all third party claims arising from the Contractor's operations, including claims resulting from the Employer's acts or omissions.",
     "high","indemnity","true","ZW","FIDIC","Indemnity extends to employer's own acts; removes employer's responsibility for its own negligence."),
    ("The Contractor shall be liable for delay damages at the stated rate from the scheduled Completion Date, whether or not the delay was caused partly by the Employer.",
     "high","delay","true","ZW","FIDIC","LADs run even where employer is partly responsible; no concurrent delay apportionment."),
    ("The Engineer's determination of any claim shall be final and binding unless challenged by a DAAB decision within 28 days.",
     "high","dispute","true","ZW","FIDIC","Short DAAB challenge window; practical difficulty in convening DAAB within 28 days in Zimbabwe."),
    ("All Contractor's Equipment brought to Site shall be deemed to be exclusively intended for use on the Works and shall not be removed without the Engineer's consent.",
     "high","payment","true","ZW","FIDIC","Deemed vesting of contractor's equipment; exposes contractor to loss on employer insolvency."),
    ("The Contractor shall bear all additional costs arising from unforeseeable physical conditions unless the Engineer certifies that such conditions could not reasonably have been foreseen by an experienced contractor.",
     "high","site_conditions","true","ZW","FIDIC","High bar for unforeseeable conditions relief; Engineer's gatekeeping removes automatic entitlement."),
    ("The rate of delay damages shall be 0.5% per day of the Accepted Contract Amount, uncapped.",
     "high","delay","true","ZW","FIDIC","0.5% per day uncapped LADs; extremely high rate on large contracts."),
    ("Any claim for additional payment which is not supported by contemporary records shall be rejected by the Engineer.",
     "high","payment","true","ZW","FIDIC","Contemporary records as condition precedent; records often not maintained adequately on site."),
    ("The Contractor shall provide a Performance Security equal to 15% of the Accepted Contract Amount.",
     "high","administrative","true","ZW","FIDIC","15% performance security is above FIDIC standard 10%; significant liquidity cost."),
]

FIDIC_MEDIUM = [
    ("The Engineer shall respond to the Contractor's claim within 42 days of receiving the fully detailed claim; failure to respond shall be deemed a rejection.",
     "medium","delay","false","ZW","FIDIC","FIDIC 2017 Clause 20.2.5 response period; deemed rejection protects contractor's programme certainty."),
    ("The Contractor shall give a Notice of Claim as soon as practicable and in any event within 28 days of the event or circumstance first arising.",
     "medium","delay","false","ZW","FIDIC","28-day CE notification obligation; standard FIDIC time bar."),
    ("If the Contractor fails to comply with a Time for Completion, the Employer may after notice reduce the Performance Security proportionally.",
     "medium","delay","true","ZW","FIDIC","Bond reduction on delay; some risk but subject to notice and proportionality."),
    ("The Contractor shall submit a detailed breakdown of any claim for additional Cost within 84 days of the claim notice.",
     "medium","delay","false","ZW","FIDIC","84-day detailed claim submission; reasonable period for complex cost substantiation."),
    ("The Employer shall make an Advance Payment of 10% of the Accepted Contract Amount within 21 days of receipt of the Performance Security.",
     "medium","payment","false","ZW","FIDIC","FIDIC advance payment at 10%; standard and contractor-supportive."),
    ("The Contractor may refer a dispute to the DAAB at any time; the DAAB shall give its decision within 84 days of referral.",
     "medium","dispute","false","ZW","FIDIC","DAAB mechanism; structured independent dispute resolution."),
    ("Extensions of Time shall be granted for Exceptional Events and other matters set out in Sub-Clause 8.5.",
     "medium","delay","false","ZW","FIDIC","Standard FIDIC EOT provision covering listed relief events."),
    ("The Engineer shall issue Payment Certificates within 28 days of receiving the Contractor's Statement.",
     "medium","payment","false","ZW","FIDIC","28-day certification period; standard FIDIC payment cycle."),
    ("The Employer shall pay the Contractor within 56 days of the Engineer issuing a Payment Certificate.",
     "medium","payment","false","ZW","FIDIC","56-day payment period; on the longer side under FIDIC Red Book."),
    ("The Contractor shall give a Defect Notice to the Engineer within 28 days of discovering a defect caused by the Employer.",
     "medium","warranty","false","ZW","FIDIC","Contractor's defect notification right; protects against employer-caused damage being passed back."),
]

FIDIC_LOW = [
    ("The Employer shall provide the Site to the Contractor on or before the Commencement Date.",
     "low","administrative","false","ZW","FIDIC","Standard FIDIC site possession obligation; employer duty."),
    ("The Engineer shall act neutrally between the parties in all matters under this Contract.",
     "low","administrative","false","ZW","FIDIC","FIDIC 2017 engineer neutrality obligation; fundamental balanced provision."),
    ("The Contractor shall execute the Works in accordance with the Contract and the Engineer's instructions.",
     "low","administrative","false","ZW","FIDIC","Fundamental contractor obligation; standard."),
    ("The Employer shall pay the amounts certified by the Engineer in accordance with the Contract.",
     "low","payment","false","ZW","FIDIC","Employer's fundamental payment obligation; standard."),
    ("Both Parties shall endeavour to avoid disputes by prompt and amicable resolution of issues.",
     "low","dispute","false","ZW","FIDIC","Dispute avoidance obligation; aspirational and balanced."),
    ("The Contractor shall comply with all applicable laws, regulations and permit conditions throughout the Contract.",
     "low","regulatory","false","ZW","FIDIC","General regulatory compliance; standard obligation."),
    ("The Contractor shall take full responsibility for the adequacy, stability and safety of all site operations.",
     "low","indemnity","false","ZW","FIDIC","Safety responsibility; fundamental contractor duty."),
    ("The Contractor shall provide all Equipment and Temporary Works needed for execution of the Works.",
     "low","administrative","false","ZW","FIDIC","Equipment provision obligation; standard."),
    ("The Engineer may issue a Taking-Over Certificate when the Works are substantially complete.",
     "low","delay","false","ZW","FIDIC","Taking-over certification; milestone trigger for risk transfer."),
    ("After the Taking-Over Certificate is issued, risk of loss or damage to the Works shall pass to the Employer.",
     "low","indemnity","false","ZW","FIDIC","Risk transfer on taking-over; standard FIDIC risk allocation."),
]

FIDIC_OPPORTUNITY = [
    ("Where the Employer fails to provide the Site by the agreed date, the Contractor is entitled to an extension of time and Cost plus profit.",
     "opportunity","delay","false","ZW","FIDIC","Full recovery (time + cost + profit) for employer's failure to provide site; strong contractor protection."),
    ("Where the Engineer fails to respond within the period for reply, the Contractor may treat the absence of response as approval of the communication.",
     "opportunity","variation","true","ZW","FIDIC","Deemed approval on engineer inaction; contractor can proceed on basis of non-response."),
    ("The Contractor is entitled to additional Cost if it encounters physical conditions which could not have been foreseen by an experienced contractor.",
     "opportunity","site_conditions","false","ZW","FIDIC","Unforeseeable physical conditions relief; standard FIDIC 4.12 protection."),
    ("Where changes in Laws after the Base Date increase the Contractor's Costs, the Contract Price shall be adjusted accordingly.",
     "opportunity","regulatory","false","ZW","FIDIC","Change-in-law risk on employer; contractor protected from sovereign risk after Base Date."),
    ("The Contractor is entitled to Exceptional Event relief for epidemics, natural catastrophes, wars, embargoes and acts of government.",
     "opportunity","force_majeure","false","ZW","FIDIC","Broad exceptional event relief including government action; relevant for Zimbabwe sovereign risk."),
]

FIDIC_NEUTRAL = [
    ("GENERAL CONDITIONS OF CONTRACT","neutral","administrative","false","ZW","FIDIC","Document heading."),
    ("PART I – GENERAL CONDITIONS","neutral","administrative","false","ZW","FIDIC","FIDIC structure heading."),
    ("PART II – PARTICULAR CONDITIONS","neutral","administrative","false","ZW","FIDIC","FIDIC particular conditions heading."),
    ("CLAUSE 1 – GENERAL PROVISIONS","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("CLAUSE 2 – THE EMPLOYER","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("CLAUSE 3 – THE ENGINEER","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("CLAUSE 4 – THE CONTRACTOR","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("CLAUSE 8 – COMMENCEMENT, DELAYS AND SUSPENSION","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("CLAUSE 14 – CONTRACT PRICE AND PAYMENT","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("CLAUSE 20 – EMPLOYER'S AND CONTRACTOR'S CLAIMS","neutral","administrative","false","ZW","FIDIC","FIDIC section heading."),
    ("'Accepted Contract Amount' means the amount accepted in the Letter of Acceptance for the execution and completion of the Works and the remedying of any defects.",
     "neutral","administrative","false","ZW","FIDIC","Standard FIDIC definition."),
    ("'Engineer' means the person appointed by the Employer to act as the Engineer for the purposes of the Contract, as named in the Contract Data.",
     "neutral","administrative","false","ZW","FIDIC","Standard FIDIC engineer definition."),
    ("'Base Date' means the date 28 days before the latest date for submission of the Tender.",
     "neutral","administrative","false","ZW","FIDIC","Standard FIDIC Base Date definition; triggers change-in-law risk allocation."),
    ("'Defects Notification Period' means the period for notifying defects in the Works or a Section as stated in the Contract Data.",
     "neutral","administrative","false","ZW","FIDIC","Standard FIDIC DNP definition."),
    ("'Time for Completion' means the time for completing the Works or a Section as stated in the Contract Data, adjusted under Sub-Clause 8.5.",
     "neutral","administrative","false","ZW","FIDIC","Standard FIDIC completion time definition."),
]

# ── additional clause expansions ──────────────────────────────────────────────

EXTRA_JCT_HIGH = [
    ("The Contractor shall not make any claim for loss and expense arising from delay to the Works unless a detailed programme showing critical path analysis is submitted with the claim.",
     "high","delay","true","UK","JCT","Critical path programme as condition precedent to loss and expense; places impossible evidential burden on contractor."),
    ("The Contractor warrants that all subcontractors and suppliers will perform their obligations; the Contractor shall be liable for all defaults of subcontractors as if they were the Contractor's own defaults.",
     "high","indemnity","true","UK","JCT","Full vicarious liability for subcontractor defaults; removes contractor's ability to claim against employer for nominated sub failures."),
    ("The Employer may instruct the Contractor to accelerate the programme; the Contractor shall comply and any claim for acceleration costs shall be submitted within 7 days of the instruction.",
     "high","delay","true","UK","JCT","7-day acceleration claim window is impractical; employer can demand acceleration without pre-agreeing cost."),
    ("Where the Contractor submits a payment application that the Employer considers to be exaggerated, the Employer may reduce all future applications by 20% as a penalty.",
     "high","payment","true","UK","JCT","Punitive 20% reduction on future applications; disproportionate response to disputed valuations."),
    ("The Contractor shall not be entitled to any uplift on the rates and prices in the Contract Bills for any variation, regardless of the nature, complexity or volume of the varied work.",
     "high","variation","true","UK","JCT","Fixed-rate variations with no uplift for changed conditions; erodes contractor margin on complex variations."),
    ("The Defects Liability Period shall be extended by the period of any defect rectification; a single recurring defect may extend the DLP indefinitely.",
     "high","warranty","true","UK","JCT","Rolling DLP extension creates perpetual warranty exposure; no limit on total DLP duration."),
    ("The Contractor shall be responsible for the security of the entire Site, including all Employer-stored materials, and shall indemnify the Employer for any theft or loss on Site.",
     "high","indemnity","true","UK","JCT","Security indemnity for employer's materials; imposes insurance cost for employer's own property."),
    ("Where practical completion is delayed, the Employer may call upon the performance bond in full without proving loss.",
     "high","administrative","true","UK","JCT","On-demand bond call without proof of loss; contractor's bond is vulnerable to abuse."),
    ("The Contractor shall repay all amounts received under interim certificates if the final account shows the total certified was overpaid, with interest at 8% above base rate.",
     "high","payment","true","UK","JCT","Retroactive overpayment recovery with punitive interest; creates cash flow uncertainty throughout project."),
    ("The Contractor's liability shall not be limited under any circumstances; any contractual cap on liability is expressly excluded.",
     "high","indemnity","true","UK","JCT","Removal of any liability cap; contractor faces unlimited financial exposure."),
]

EXTRA_NEC4_HIGH = [
    ("The Project Manager may instruct the Contractor to use a different method of working without it being a compensation event if the change is necessary for safety.",
     "high","variation","true","UK","NEC4","Safety-based method change without CE; employer defines 'necessary' unilaterally."),
    ("The Contractor shall submit all CE quotations within 21 days; late submission means the PM's own assessment is binding on the Contractor without review.",
     "high","variation","true","UK","NEC4","PM's assessment binding on late quotation; removes contractor's ability to challenge PM's figures."),
    ("The Contractor shall maintain the Accepted Programme; failure to maintain an accepted programme for more than 4 weeks results in a reduction in the PWDD of 15%.",
     "high","delay","true","UK","NEC4","15% PWDD reduction for programme lapse; punitive financial sanction for administrative failure."),
    ("No CE shall arise from any instruction given orally by the Project Manager; all instructions must be in writing and logged in the Risk Register.",
     "high","variation","true","UK","NEC4","Oral instruction exclusion; contractors regularly act on PM oral instructions on live sites."),
    ("The Contractor's share of any cost overrun shall be 100% for the first 10% of overrun and 50% thereafter; the Employer's share of savings is 70%.",
     "high","payment","true","UK","NEC4","Asymmetric pain/gain share highly unfavourable to contractor; 100% pain on first 10% with only 30% gain."),
]

EXTRA_BESPOKE_HIGH = [
    ("The Contractor shall not be entitled to any additional payment for compliance with any new law, regulation or standard enacted after the Contract Date.",
     "high","regulatory","true","ZW","bespoke","Full post-contract regulatory risk on contractor; particularly dangerous in Zimbabwe's evolving regulatory environment."),
    ("All disputes shall be resolved by a sole arbitrator appointed by the Employer; the Employer's selection shall be final and not subject to challenge.",
     "high","dispute","true","ZW","bespoke","Employer-appointed sole arbitrator; fundamentally compromises independence of arbitration."),
    ("Payment shall only be made quarterly; no interim payments shall be due during the Contract Period regardless of the value of work executed.",
     "high","payment","true","ZW","bespoke","Quarterly payment cycle; creates severe cash flow hardship for contractor, particularly in Zimbabwe's inflation environment."),
    ("The Contractor shall rectify all defects notified during the Defects Liability Period at its own cost, including defects caused by fair wear and tear, acts of God or third parties.",
     "high","warranty","true","ZW","bespoke","Warranty extends to fair wear and tear and force majeure damage; far beyond standard contractor warranty obligations."),
    ("The Employer may reduce the scope of Works by up to 75% without giving reasons and without any adjustment to the Contract Price for preliminaries or overheads.",
     "high","variation","true","ZW","bespoke","75% omission right without overhead recovery; contractor's fixed costs entirely at employer's risk."),
    ("The Contractor shall bear all costs of independent testing regardless of the test results; no cost recovery applies where tests confirm compliance.",
     "high","variation","true","ZW","bespoke","All testing costs on contractor; creates financial disincentive to test and verify compliance."),
    ("Any claim not submitted within 14 days of the cause of action arising is time-barred and shall not be considered.",
     "high","delay","true","ZW","bespoke","14-day claim bar is impractically short; causes loss of legitimate claims on complex projects."),
    ("The Contractor warrants that all rates in the Schedule of Rates are adequate and shall not be entitled to any adjustment for unforeseeable increases in cost.",
     "high","payment","true","ZW","bespoke","Fixed-rate warranty removes all cost risk adjustment mechanisms; dangerous in Zimbabwe's volatile material cost environment."),
]

EXTRA_PAYMENT = [
    ("Payment applications must be submitted in the prescribed format using the Employer's software system; applications in any other format shall not constitute valid applications.",
     "high","payment","true","UK","JCT","Format condition precedent on payment applications; employer can reject valid applications on technical grounds."),
    ("The Employer shall certify and pay the sum of all undisputed items in the Contractor's application pending resolution of disputed items.",
     "low","payment","false","UK","JCT","Undisputed sum payment obligation; protects contractor's cash flow during valuation disputes."),
    ("Interest shall accrue on certified but unpaid sums at LIBOR plus 2% from the due date for payment.",
     "medium","payment","false","UK","NEC4","Interest on overdue sums; LIBOR-linked rate is market standard."),
    ("The Contractor shall not commence any variation until the value has been pre-agreed in writing; no post-hoc valuation claims shall be entertained.",
     "high","variation","true","ZW","bespoke","Pre-agreed VO pricing condition precedent; prevents urgent variations proceeding without agreed cost."),
    ("The final account shall be settled within 180 days of the issue of the Defects Certificate; any disputed items shall be referred to adjudication.",
     "medium","payment","false","UK","JCT","180-day final account settlement with adjudication backstop; reasonable overall."),
    ("The Contractor shall submit a monthly cost report showing actual versus forecast expenditure, certified by the Contractor's quantity surveyor.",
     "low","payment","false","ZW","FIDIC","Cost reporting obligation; transparency tool."),
    ("Where the exchange rate moves by more than 5% against the Contractor between the Base Date and the payment date, the Contract Price shall be adjusted by the difference.",
     "opportunity","payment","false","ZW","FIDIC","Exchange rate fluctuation protection; strong safeguard for international contracts in Zimbabwe."),
    ("No payment shall be made for materials off-site unless the Contractor provides proof of insurance, vesting certificate and list of materials.",
     "medium","payment","false","UK","JCT","Off-site materials payment conditions; reasonable certification requirements."),
    ("The Contractor shall be entitled to a pre-agreed sum for demobilisation costs payable on Practical Completion.",
     "opportunity","payment","false","ZW","bespoke","Express demobilisation payment; reduces contractor's post-completion financial exposure."),
    ("All payments shall be subject to deduction of withholding tax at the rate applicable under Zimbabwe Revenue Authority regulations.",
     "medium","payment","false","ZW","bespoke","ZIMRA withholding tax deduction; statutory requirement reducing contractor's net receipts."),
]

EXTRA_FORCE_MAJEURE = [
    ("Force majeure events include epidemic, pandemic, earthquake, flood, fire, war, civil commotion, sanctions, government action and any other event beyond the reasonable control of the affected party.",
     "low","force_majeure","false","ZW","bespoke","Broad force majeure definition including government action; well-suited to Zimbabwe's political risk environment."),
    ("If a force majeure event continues for more than 90 days, either party may terminate the Contract by giving 14 days' notice; the Contractor shall be paid for work completed.",
     "low","force_majeure","false","ZW","bespoke","Bilateral termination right on prolonged force majeure; contractor recovers value of work done."),
    ("The Contractor shall not be entitled to additional cost arising from a force majeure event; its sole entitlement is an extension of time.",
     "medium","force_majeure","true","ZW","bespoke","Time-only relief for force majeure; contractor bears standing cost during FM period."),
    ("COVID-19 and any variant thereof shall not constitute a force majeure event for the purposes of this Contract.",
     "high","force_majeure","true","UK","JCT","Pandemic exclusion from force majeure; leaves contractor exposed to pandemic disruption costs."),
    ("Where a force majeure event affects both parties, each shall bear its own costs and no claim shall be made against the other.",
     "medium","force_majeure","false","ZW","FIDIC","Bilateral cost-bearing on shared FM events; balanced loss allocation."),
    ("The Contractor shall give notice of a force majeure event within 14 days of its commencement; failure to give notice within this period shall disentitle the Contractor from any relief.",
     "medium","force_majeure","true","UK","JCT","14-day FM notice as condition precedent; strict but proportionate."),
    ("Unavailability of foreign currency shall constitute a force majeure event under this Contract.",
     "opportunity","force_majeure","false","ZW","bespoke","Forex unavailability as FM event; critical protection for Zimbabwe contracts."),
    ("Hyperinflationary conditions that render the Contract commercially impossible to perform shall constitute a force majeure event.",
     "opportunity","force_majeure","false","ZW","bespoke","Hyperinflation as FM event; Zimbabwe-specific protection for contractor."),
    ("Government-imposed price controls that prevent the Contractor from procuring materials at market prices shall entitle the Contractor to an adjustment of the Contract Price.",
     "opportunity","regulatory","false","ZW","bespoke","Price control risk on employer; government intervention risk passed back to employer."),
    ("The Contractor shall maintain contingency resources and plans to mitigate force majeure events to the extent reasonably practicable.",
     "low","force_majeure","false","UK","NEC4","FM mitigation obligation; reasonable and standard."),
]

EXTRA_WARRANTY = [
    ("The Contractor provides a 10-year structural warranty for all reinforced concrete works in accordance with the relevant British Standards.",
     "medium","warranty","false","UK","JCT","Long-form structural warranty; common on residential and commercial developments."),
    ("The Contractor shall provide collateral warranties to the Employer's funders and tenants in the form annexed to this Contract.",
     "medium","warranty","false","UK","JCT","Collateral warranty obligation; standard on commercial developments."),
    ("All mechanical and electrical plant and equipment shall be warranted against defects for a period of 24 months from the date of commissioning.",
     "medium","warranty","false","ZW","bespoke","Extended M&E warranty; common on process plant and building services."),
    ("The Contractor shall maintain professional indemnity insurance in the sum of USD 500,000 for 6 years following Practical Completion.",
     "medium","indemnity","false","ZW","bespoke","PI insurance obligation post-completion; standard on design-and-build contracts."),
    ("Any defect that recurs within 12 months of rectification shall be treated as a new defect with a fresh 12-month rectification warranty.",
     "high","warranty","true","UK","JCT","Rolling warranty on recurring defects; creates perpetual exposure for systemic defects."),
    ("The Defects Liability Period for roofing works shall be 5 years from Practical Completion.",
     "medium","warranty","false","ZW","bespoke","Extended DLP for specialist trade; common on roofing and waterproofing."),
    ("The Contractor shall provide product warranties from all specialist suppliers in the Employer's name for a minimum of 10 years.",
     "medium","warranty","false","UK","JCT","Third-party warranty assignment obligation; requires supplier co-operation."),
    ("The Contractor's liability for latent defects shall survive the Defects Certificate and continue for 6 years from the date of Practical Completion.",
     "medium","warranty","false","UK","JCT","Latent defect liability period; standard under Limitation Act 1980."),
    ("The Contractor warrants that the completed Works will achieve the energy performance rating specified in the Employer's Requirements.",
     "medium","warranty","true","UK","JCT","Performance warranty; creates ongoing liability if building underperforms."),
    ("The Contractor accepts no warranty liability for defects arising from the Employer's design or specification.",
     "opportunity","warranty","false","UK","JCT","Design warranty carve-out for employer-provided design; fair on contractor."),
]

EXTRA_TERMINATION = [
    ("On termination by the Contractor for Employer default, the Contractor shall be entitled to recover its costs, loss of profit on the remaining Works, and reasonable demobilisation costs.",
     "opportunity","termination","false","UK","JCT","Full termination entitlement for contractor on employer default; standard JCT 8.9 protection."),
    ("The Employer may terminate the Contract if the Contractor is in material breach and fails to remedy the breach within 14 days of written notice.",
     "medium","termination","false","UK","JCT","Standard termination for cause with 14-day cure period; balanced provision."),
    ("The Contractor may terminate if the Employer fails to pay a certified sum within 28 days of the final date for payment after 14 days' notice.",
     "opportunity","termination","false","UK","JCT","Contractor termination right for employer non-payment; standard protection."),
    ("On any termination, the Employer shall pay the Contractor within 28 days for all work properly executed and materials delivered to site.",
     "low","termination","false","ZW","bespoke","Payment on termination obligation; standard and reasonable."),
    ("If the Contractor becomes insolvent, the Employer shall have the right to complete the Works using the Contractor's workforce and equipment without further payment.",
     "high","termination","true","UK","JCT","Employer's step-in right using contractor's resources without additional payment; commercially punitive."),
    ("The Employer may suspend the Works for any reason for up to 60 days without this constituting a termination; during suspension the Contractor shall stand down without payment.",
     "high","payment","true","ZW","bespoke","Unpaid suspension right; contractor bears standing costs during employer-requested suspension."),
    ("Either party may terminate if a force majeure event continues for more than 180 days, with the Contractor entitled to all costs incurred to the termination date.",
     "low","termination","false","ZW","FIDIC","FM termination after 180 days with full cost recovery; balanced and reasonable."),
    ("The Contractor shall not terminate the Contract for any reason without first obtaining a court order declaring the Employer to be in breach.",
     "high","termination","true","ZW","bespoke","Court order condition precedent to contractor termination; practically removes contractor's self-help termination right."),
    ("On termination for employer convenience, the Contractor shall be entitled to the value of work executed, materials on site, reasonable overheads and 10% of the remaining works as lost profit.",
     "opportunity","termination","false","ZW","bespoke","Generous termination for convenience entitlement including lost profit; contractor-favourable."),
    ("The Employer's right to terminate shall not arise where the alleged breach is caused by the Employer's own act or omission.",
     "opportunity","termination","false","UK","JCT","Employer's concurrent breach prevents termination; protects contractor where employer contributes to the breach."),
]

EXTRA_DISPUTE = [
    ("All disputes shall be resolved by adjudication in accordance with the Scheme for Construction Contracts (England and Wales) Regulations 1998.",
     "low","dispute","false","UK","JCT","HGCRA-compliant adjudication clause; statutory right preserved."),
    ("Either party may give notice of adjudication at any time; the adjudicator shall be appointed by the RICS within 5 days of the notice.",
     "low","dispute","false","UK","NEC4","Standard RICS adjudicator nomination; balanced and practical."),
    ("Arbitration shall be conducted under the Zimbabwe Arbitration Act [Chapter 7:15] and the rules of the Arbitration Foundation of Southern Africa (AFSA).",
     "low","dispute","false","ZW","bespoke","Zimbabwe arbitration framework; appropriate institutional rules for regional commercial disputes."),
    ("The seat of arbitration shall be Harare, Zimbabwe; the arbitrator shall have authority to grant interim relief.",
     "low","dispute","false","ZW","bespoke","Harare-seated arbitration; appropriate for Zimbabwe construction disputes."),
    ("Either party may apply to the High Court of Zimbabwe for urgent interim relief pending arbitration.",
     "low","dispute","false","ZW","bespoke","Preservation of urgent court relief; balanced dispute mechanism."),
    ("All disputes shall be finally resolved by a panel of three arbitrators appointed by the ICC; the Contractor waives the right to challenge any ICC appointment.",
     "medium","dispute","true","ZW","FIDIC","ICC arbitration with waiver of appointment challenge; reduces contractor's procedural rights."),
    ("Disputes shall first be referred to a technical expert for determination within 30 days; expert determination shall be binding unless overturned by arbitration.",
     "medium","dispute","false","ZW","bespoke","Expert determination as first-tier; efficient mechanism for technical disputes."),
    ("The Contractor shall continue to work diligently pending resolution of any dispute and shall not suspend work merely because a dispute exists.",
     "medium","dispute","true","ZW","bespoke","Work continuation obligation during disputes; limits contractor's leverage but maintains project progress."),
    ("The losing party shall bear all costs of arbitration including the other party's legal fees assessed on an indemnity basis.",
     "medium","dispute","false","UK","JCT","Indemnity costs order by arbitrator; increases stakes of losing a dispute."),
    ("Good faith negotiation shall be a condition precedent to arbitration; parties shall negotiate for 30 days before initiating formal proceedings.",
     "low","dispute","false","ZW","bespoke","Negotiation condition precedent; promotes amicable resolution before formal proceedings."),
]

# ── assemble all clause libraries ─────────────────────────────────────────────

ALL_CLAUSES = (
    JCT_HIGH + JCT_MEDIUM + JCT_LOW + JCT_OPPORTUNITY + JCT_NEUTRAL +
    NEC4_HIGH + NEC4_MEDIUM + NEC4_LOW + NEC4_OPPORTUNITY + NEC4_NEUTRAL +
    BESPOKE_ZW_HIGH + BESPOKE_ZW_MEDIUM + BESPOKE_ZW_LOW + BESPOKE_ZW_OPPORTUNITY + BESPOKE_ZW_NEUTRAL +
    FIDIC_HIGH + FIDIC_MEDIUM + FIDIC_LOW + FIDIC_OPPORTUNITY + FIDIC_NEUTRAL +
    EXTRA_JCT_HIGH + EXTRA_NEC4_HIGH + EXTRA_BESPOKE_HIGH +
    EXTRA_PAYMENT + EXTRA_FORCE_MAJEURE + EXTRA_WARRANTY + EXTRA_TERMINATION + EXTRA_DISPUTE
)

print(f"Base clause library: {len(ALL_CLAUSES)} unique clauses")

# ── generate variations ───────────────────────────────────────────────────────

def vary_amount(s):
    amounts = ["USD 50,000","USD 100,000","USD 250,000","USD 500,000","USD 1,000,000",
               "£50,000","£100,000","£250,000","£500,000","£1,000,000",
               "ZAR 500,000","USD 75,000","USD 150,000"]
    percents = ["5%","10%","12.5%","15%","20%","2.5%","7.5%"]
    days = ["7 days","14 days","21 days","28 days","42 days","48 hours","72 hours"]
    rates = ["0.1%","0.2%","0.5%","1%","0.25%","0.15%"]
    s2 = s
    for a in ["USD 50,000","USD 100,000","£50,000","10%","28 days","0.5%"]:
        if a in s2:
            if "%" in a and "%" in s2:
                s2 = s2.replace(a, random.choice(percents), 1)
            elif "days" in a:
                s2 = s2.replace(a, random.choice(days), 1)
            elif "USD" in a or "£" in a:
                s2 = s2.replace(a, random.choice(amounts), 1)
            elif "0." in a:
                s2 = s2.replace(a, random.choice(rates), 1)
            break
    return s2

# generate variations of existing clauses to pad toward 10k
VARIATIONS = []
target = 10000
real_count = 505  # approximate
needed_generated = target - real_count
base_len = len(ALL_CLAUSES)

random.shuffle(ALL_CLAUSES)

# First pass: all base clauses
GENERATED = [list(c) for c in ALL_CLAUSES]

# Second pass: varied versions
while len(GENERATED) < needed_generated:
    src = random.choice(ALL_CLAUSES)
    varied_text = vary_amount(src[0])
    if varied_text != src[0]:
        row = list(src)
        row[0] = varied_text
        GENERATED.append(row)
    else:
        # light paraphrase by prepending context label — skip neutral headings
        if src[1] == 'neutral':
            GENERATED.append(list(src))
            continue
        prefixes = [
            "The parties agree that ", "It is hereby agreed that ",
            "For the avoidance of doubt, ", "Notwithstanding any other provision, ",
            "Subject to the terms of this Contract, ", "In accordance with industry practice, ",
            "Without limiting the generality of the foregoing, "
        ]
        row = list(src)
        pfx = random.choice(prefixes)
        first = src[0][0]
        rest = src[0][1:]
        new_text = pfx + first.lower() + rest
        row[0] = new_text
        GENERATED.append(row)

print(f"Generated clause rows: {len(GENERATED)}")

# ── read and transform real rows ──────────────────────────────────────────────

REAL_ROWS = []
with open('sorted_dataset.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        if len(row) >= 4 and row[3].strip() not in ('', 'synthetic'):
            mapped = map_real_row(row)
            if mapped:
                REAL_ROWS.append(mapped)

print(f"Real rows retained: {len(REAL_ROWS)}")

# ── combine and write output ───────────────────────────────────────────────────

HEADER = ['text','risk_level','clause_type','one_sided','jurisdiction','contract_type','notes']

all_rows = REAL_ROWS + [[g[0],g[1],g[2],g[3],g[4],g[5],g[6]] for g in GENERATED]
random.shuffle(all_rows)
# Trim to exactly 10000
all_rows = all_rows[:10000]

with open('construction_contracts_dataset.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    writer.writerow(HEADER)
    writer.writerows(all_rows)

print(f"\nFinal dataset written: {len(all_rows)} rows")

# distribution summary
from collections import Counter
rl_count = Counter(r[1] for r in all_rows)
ct_count = Counter(r[5] for r in all_rows)
print("\nRisk level distribution:")
for k,v in sorted(rl_count.items()): print(f"  {k:12s}: {v:5d} ({100*v/len(all_rows):.1f}%)")
print("\nContract type distribution:")
for k,v in sorted(ct_count.items()): print(f"  {k:12s}: {v:5d} ({100*v/len(all_rows):.1f}%)")
