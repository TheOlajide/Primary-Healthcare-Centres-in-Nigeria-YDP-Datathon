# Primary Healthcare Centres in Nigerua
## Navigation
- [Overview](#overview)
- [Technologies](#technologies)
- [Methodology](#methodology)
- [Dashboard Preview](#dashboard-preview)
- [Key Insights](#key-insights)
- [Conclusion](#conclusion)
- [Recommendations](#recommendations)

## Overview

Primary Healthcare Centres (PHCs) serve as the first point of contact for healthcare for many Nigerians. However, gaps in data collection, reporting, and visibility into facility-level conditions can make it difficult for health stakeholders to understand where support is most urgently needed.

This project aims to develop a data-driven solution that captures information directly from healthcare facilities and establishes a **hierarchical reporting system from individual PHCs through Local Government Areas (LGAs) to the national level**.

The solution focuses on key indicators such as medicine and vaccine stock levels, staffing adequacy, operational status, service readiness, and facility resources. It also aims to identify missing, incomplete, or delayed reports, helping stakeholders distinguish between facilities facing operational challenges and facilities whose conditions are simply unknown due to reporting gaps.

By transforming facility-level data into actionable metrics, the project seeks to provide health planners and decision-makers with a clearer picture of PHC conditions across Nigeria. These insights can support more informed decisions on resource allocation, funding, medicine and vaccine restocking, workforce deployment, and targeted interventions.

Ultimately, the goal is to improve visibility, strengthen accountability in healthcare reporting, and help ensure that resources reach the facilities and communities that need them most.

## Technologies

### 1. Data Collection

- **Synthetic Data:** Generated PHC facility-level data informed by medical journals and research on Primary Healthcare Centres in Nigeria. The dataset simulates information on facility operations, staffing, medicine and vaccine inventory, and service readiness.

### 2. Data Transformation, Orchestration, and Storage

- **Microsoft OneDrive:** Serves as the raw data landing zone, with folders organized by Local Government Area (LGA) to represent facility-level reporting within the local government hierarchy.

- **Dataflow Gen2:** Acts as the data transformation layer, processing raw data files and preparing structured tables for storage in the Lakehouse.

- **Microsoft Fabric Lakehouse:** Stores refined data tables organized into the Silver and Gold layers, supporting data quality, transformation, and downstream analytics.

- **Data Pipeline:** Orchestrates the data workflow, coordinating transformation and storage processes to move data through the pipeline.

### 3. Data Modelling and Visualization

- **Semantic Model:** Defines table relationships and the analytical structure used to calculate metrics and support reporting.

- **Power BI:** Connects to the semantic model using Direct Lake to deliver interactive report/insights into PHC operational status, medicine and vaccine availability, staffing adequacy, service readiness, and facility risk.

```
          Source Data
          ───────────
    Synthetic PHC Facility Data
      (Facility-Level Records)
                 │
                 ▼
   Storage / Transformation
   ────────────────────────
          [Microsoft OneDrive]
             (Raw Data)
                 │
                 ▼
          [Dataflow Gen2]
          (Transformation)
                 │
                 ▼
      [Microsoft Fabric Lakehouse]
        (Silver / Gold Tables)
                 │
                 ▼
          Visualization
          ─────────────
          [Semantic Model]
        (Relationships / Measures)
                 │
                 ▼
             [Power BI]
         (Dashboards / Reports)
```

## Methodology

According to an Health Journal on PHC Centres in Nigeria, Nigeria had approximately 34,076 Primary Healthcare Centres (PHCs), estimated 6,815 (20%) considered fully functional. The source also highlights signifi cant gaps in essential equipment and supplies required for PHC operations, including medicines and basic medical equipment. These figures were used as contextual baseline for synthesizing the data used for this project.

The geographical structure of the dataset was based on the Nigeria Administrative Divisions dataset (github), which identifies 36 states and the Federal Capital Territory, 774 Local Government Areas (LGAs), and 8,799 wards.

The data was then dumped in a Microsoft OneDrive, simulating a scenario where each facility has dedicated sub folders for each local government.
A shortcut is created in the file section of Fabric Lakehouse where these data can be inferred without worrying about the overhead of copying into fabric. This lakehouse files serves as the staging/bronze layer.

Dataflow gen 2 is used to transform the staged data, and then moved into a table in Lakehouse. These tables serve as our silver/gold refined layer for analytics. A semantic model is formed on them and powerbi consumes directly.

For visualization, a direct lake connection is established in powerbi desktop, to enable a sync while working locally. Reporting is done on powerbi and published to the lakehouse workspace.


![alt text](<report/PHC Data Pipeline Architecture Infographic.png>)

*Infographic Image of Data Pipeline.*

### Derivation of Key Metrics

This section explains the methodology used to derive five important metrics in the PHC dashboard: Overall PHC Risk Score, High-Risk Facilities, Vaccine/Medicine Shortage Rate, Overall Service Readiness Score, and Staffing Adequacy. It also documents the Medicine and Vaccine Shortage Rates and explains how geographic drill-downs support more detailed analysis.

### 1. Overall PHC Risk Score

The Overall PHC Risk Score measures the combined operational risk of Primary Healthcare Centres (PHCs) across four dimensions: medicine availability, vaccine availability, staffing adequacy, and service readiness.

The score is calculated on a scale of 0–100, with each dimension assigned a predefined weight according to its contribution to the overall risk assessment.

#### 1.1 Risk Dimensions and Weights

| Risk Dimension | Weight |
|---|---:|
| Medicine Risk | 30% |
| Vaccine Risk | 20% |
| Staffing Risk | 25% |
| Service-Readiness Risk | 25% |
| **Total** | **100%** |

#### 1.2 Overview of the PHC Risk Scoring Framework

The following diagram illustrates how the four risk dimensions contribute to the Overall PHC Risk Score and how the resulting score is classified into Low, Medium, and High Risk categories. All four dimensions contribute directly to the final score through a weighted calculation.

```
                         ┌─────────────────────┐
                         │    PHC FACILITY     │
                         └──────────┬──────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
           ▼                        ▼                        ▼
    Medicine Risk             Vaccine Risk             Staffing Risk
        30%                       20%                      25%
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │
                                    │
                          ┌─────────┴─────────┐
                          │                   │
                          ▼                   ▼
                  Service-Readiness Risk      │
                          25%                 │
                          │                   │
                          └─────────┬─────────┘
                                    │
                                    ▼
                         ┌────────────────────┐
                         │  OVERALL PHC RISK  │
                         │       SCORE        │
                         │       0–100        │
                         └──────────┬─────────┘
                                    │
                   ┌────────────────┼────────────────┐
                   │                │                │
                   ▼                ▼                ▼
                Low Risk        Medium Risk       High Risk
                 0–39             40–69             70–100
```

*Overview of the PHC Risk Scoring Framework.*

The final score is calculated as the weighted sum of the four risk dimensions. Each dimension contributes according to its assigned weight, and the resulting score is classified using the defined risk thresholds. A higher score indicates greater operational risk and may signal the need for more urgent intervention.

#### 1.3 Medicine Risk

Medicine Risk is derived from the medicine stock-status categories recorded in the dataset. Each category is assigned a risk weight that reflects the severity of the stock condition.

| Medicine Stock Status | Risk Weight |
|---|---:|
| In Stock | 0.00 |
| Low Stock | 0.40 |
| Critical | 0.75 |
| Stockout | 1.00 |

A higher risk weight indicates a more severe medicine supply gap. These weights are used to derive the medicine risk component of the Overall PHC Risk Score.

#### 1.4 Vaccine Risk

Vaccine Risk follows the same approach as Medicine Risk. Each vaccine stock-status category is assigned the corresponding risk weight:

| Vaccine Stock Status | Risk Weight |
|---|---:|
| In Stock | 0.00 |
| Low Stock | 0.40 |
| Critical | 0.75 |
| Stockout | 1.00 |

The assigned weights represent the severity of vaccine stock conditions and contribute to the overall risk calculation.

#### 1.5 Staffing Risk

Staffing Risk is derived from the Staffing Adequacy Score. It represents the inverse of staffing adequacy: as staffing adequacy decreases, staffing risk increases.

**Formula:**

Staffing Risk = 1 − Staffing Adequacy Score

The calculation assumes that Staffing Adequacy is expressed as a normalized value between 0 and 1. The resulting risk value can then be expressed as a percentage.

#### 1.6 Service-Readiness Risk

Service-Readiness Risk is derived from the Overall Service Readiness Score. It represents the inverse of service readiness, meaning that facilities with lower readiness scores have higher service-readiness risk.

**Formula:**

Service-Readiness Risk = 1 − Service Readiness Score

As with Staffing Risk, the calculation assumes that the Service Readiness Score is normalized between 0 and 1 before the inverse is calculated.

#### 1.7 Overall Risk Score Calculation

The four risk dimensions are combined using their assigned weights.

**Formula:**

Overall PHC Risk Score =

(Medicine Risk × 30%) + (Vaccine Risk × 20%) + (Staffing Risk × 25%) + (Service-Readiness Risk × 25%)

When the individual risk dimensions are represented as normalized values between 0 and 1, the weighted result can be multiplied by 100 to produce a score on a 0–100 scale.

The resulting score represents the combined operational risk of a PHC based on the four dimensions included in the model.

#### 1.8 Risk Classification

The Overall PHC Risk Score is classified into three categories:

| Risk Score | Normalized Score | Classification |
|---|---|---|
| 0–39 | 0.00–0.39 | Low Risk |
| 40–69 | 0.40–0.69 | Medium Risk |
| 70–100 | 0.70–1.00 | High Risk |

A higher score indicates greater overall operational risk. This classification helps stakeholders distinguish between facilities that may require routine monitoring and those that may need more urgent investigation or support.

---

### 2. High-Risk Facilities

High-Risk Facilities are PHCs whose Overall PHC Risk Score falls within the High Risk classification.

This metric identifies facilities where the combined conditions of medicine availability, vaccine availability, staffing adequacy, and service readiness indicate a high level of operational risk.

**Illustrative result:** 9,183 high-risk PHCs out of 34,076 facilities, representing 26.95% of the total.

**Formula:**

High-Risk Facility Percentage = (Number of High-Risk Facilities ÷ Total Facilities) × 100

Based on the figures above, 26.95% of the facilities in the dataset are classified as high risk. This metric helps stakeholders understand the scale of the high-risk facility population and prioritize further investigation or intervention.

---

### 3. Medicine/Vaccine Stockout Rate

The Medicine/Vaccine Stockout Rate measures the proportion of vaccine inventory records classified as Stockout relative to the total number of vaccine inventory records.

**Formula:**

Medicine/Vaccine Stockout Rate = (Number of Medicine/Vaccine Records with Stock Status = Stockout ÷ Total Vaccine Inventory Records) × 100

A higher medicine/vaccine stockout rate indicates that a larger proportion of recorded vaccine inventory items have no stock available. This metric provides an inventory-level view of vaccine availability and can help identify potential supply gaps.

The Medicine/Vaccine Stockout Rate should be distinguished from the percentage of PHCs affected by medicine/vaccine stockouts. The former measures inventory records, while the latter measures facilities affected by at least one medicine/vaccine stockout. These metrics answer different questions and may produce different results.

---

### 4. Overall Service Readiness Score

The Overall Service Readiness Score represents the average service-readiness score across the facilities included in the calculation.

**Formula:**

Overall Service Readiness Score = Average of Facility Service-Readiness Scores

A higher score indicates better service readiness, while a lower score indicates greater readiness gaps. The inverse relationship between readiness and risk is reflected in the Service-Readiness Risk component of the Overall PHC Risk Score.

#### 4.1 Interpretation of Overall Readiness

The Overall Service Readiness Score provides a single summary measure of the collective service-readiness condition of the facilities included in the calculation. It helps stakeholders assess readiness at an aggregated level rather than examining every facility individually.

However, the score must be interpreted in the context of reporting completeness.

#### 4.2 Reporting Limitations

Facilities that did not submit service reports have unknown service-readiness status. Approximately 49,707 facility records were identified as having no submitted report in the relevant reporting context.

These facilities cannot automatically be treated as either ready or not ready based on missing information alone.

Consequently, the calculated readiness score may not fully represent all facilities if non-reporting facilities are excluded from the average or otherwise handled separately. Reporting completeness should therefore be considered when interpreting this metric.

---

### 5. Staffing Adequacy

Staffing Adequacy measures how the actual number of health workers compares with the defined staffing requirement for six major staff categories: doctors, nurses, midwives, pharmacists, laboratory personnel, and Community Health Workers (CHWs).

#### 5.1 Role-Specific Adequacy

Adequacy is calculated separately for each staff category by comparing the actual staff count with the required staff count.

**Formula:**

Role Adequacy = (Actual Staff Count ÷ Required Staff Count) × 100

The required staffing figures used in this project are:

| Staff Category | Required Staff Count |
|---|---:|
| Doctor | 1 |
| Nurse | 3 |
| Midwife | 2 |
| Pharmacist | 1 |
| Laboratory Personnel | 1 |
| Community Health Worker (CHW) | 2 |

These staffing requirements are project-defined benchmarks used to calculate adequacy. They should not be interpreted as official national staffing standards unless validated against an authoritative standard.

#### 5.2 Overall Staffing Adequacy Calculation

Overall Staffing Adequacy is calculated as the average of the six role-specific adequacy measures.

**Formula:**

Overall Staffing Adequacy = (Doctor Adequacy + Nurse Adequacy + Midwife Adequacy + Pharmacist Adequacy + Laboratory Adequacy + CHW Adequacy) ÷ 6

In Power BI, the measure uses the following DAX pattern:

```dax
AVERAGEX(
    {
        [Doctor Adequacy],
        [Nurse Adequacy],
        [Midwife Adequacy],
        [CHW Adequacy],
        [Pharmacist Adequacy],
        [Laboratory Adequacy]
    },
    [Value]
)
```

The resulting score summarizes staffing adequacy across the six categories. A higher score indicates that actual staffing levels are closer to, or meet, the defined requirements.

Because the overall score averages the six roles, shortages in one category may be offset by stronger adequacy in another. The overall score should therefore be considered alongside role-specific staffing measures when identifying particular workforce gaps.

---

### 6. Medicine and Vaccine Shortage Rates

Medicine and Vaccine Shortage Rates measure the extent to which recorded inventory falls below the desired stock condition. Unlike stockout rates, these metrics include inventory records classified as Low Stock, Critical, or Stockout.

#### 6.1 Medicine Shortage Rate

The Medicine Shortage Rate considers medicine inventory records with stock statuses of Low Stock, Critical, or Stockout.

**Formula:**

Medicine Shortage Rate = (Number of Medicine Records classified as Low Stock, Critical, or Stockout ÷ Total Medicine Inventory Records) × 100

#### 6.2 Vaccine Shortage Rate

The Vaccine Shortage Rate applies the same principle to vaccine inventory records, counting records classified as Low Stock, Critical, or Stockout.

**Formula:**

Vaccine Shortage Rate = (Number of Vaccine Records classified as Low Stock, Critical, or Stockout ÷ Total Vaccine Inventory Records) × 100

These metrics help identify potential supply gaps before they become complete stockouts. They also support comparisons across states, Local Government Areas (LGAs), facilities, and individual medicines or vaccines.

---

### 7. Geographic Analysis and Aggregation Limitations

Aggregated metrics provide a useful overview of PHC conditions but can conceal important differences between locations and facilities. For example, a state-level average may obscure individual PHCs experiencing severe medicine shortages, staffing gaps, or poor service readiness.

To address this limitation, the dashboard incorporates geographic filters and drill-downs across states, LGAs, and individual facilities. These allow users to move from national or state-level summaries to more localized conditions and identify where interventions may be required.

Geographic drill-downs improve visibility into the distribution of risk, but they do not independently resolve missing or incomplete reporting.

### 8. Important Considerations

The metrics described in this ReadMe are intended to support monitoring, comparison, and prioritization of PHC facilities. Some definitions and assumptions are arbitrarily chosen, supported by clear documentation discussed above.

In particular:

- **Risk weights:** The stock-status weights and dimension weights are defined by the project's risk-scoring methodology.
- **Staffing benchmarks:** Required staff counts are project-defined assumptions unless validated against official standards.
- **Missing reports:** A missing report represents an unknown condition and should not automatically be interpreted as evidence of poor facility performance.
- **Aggregation:** Overall averages can conceal individual facility-level shortages or gaps, making geographic drill-downs important.
- **Dataset context:** Where the dataset is synthetic, the resulting figures describe the project dataset and should not be presented as verified statistics for actual Nigerian PHCs.

## Dashboard Preview

Click [here](https://app.fabric.microsoft.com/view?r=eyJrIjoiNmI3ZjA4NmEtNTdlNC00NmRiLWIyMmYtMzJiZTAzZjk3ODI5IiwidCI6ImU0ZjcyZThjLTZiZjUtNGZmZS1iZjFlLWY4YWY0MzM1MDNiMyIsImMiOjh9) to interact live with dashboard.

## Key Insights

The analysis of 34,076 PHC facility records highlights significant gaps in operational functionality, staffing, infrastructure, and essential medical supplies. The key findings are:

- **Operational functionality:** Only 45% of facilities are classified as functional, while 35% are non-functional and 20% are partially functional. This places 55% of facilities outside the fully functional category.

- **Facility risk distribution:** 7,237 facilities (21.24%) are classified as high risk, while 41.87% are medium risk and 36.89% are low risk. The large medium-risk group highlights the importance of monitoring facilities before their conditions potentially deteriorate.

- **Medicine and vaccine shortages:** Medicine shortages affect 96.25% of facilities, compared with 90.45% for vaccines. However, the vaccine shortage rate is 67.47%, considerably higher than the medicine shortage rate of 41.71% — a difference of 25.76 percentage points.

- **Staffing and infrastructure gaps:** Staffing adequacy stands at 53.39%. Water availability is reported at 49.68%, electricity at 50.07%, and storage-room availability at 58.18%. These indicators highlight potential constraints on facilities' ability to deliver and sustain essential services.

- **Geographical variation:** Risk and readiness differ across states. Among the selected state-level results, Ondo records an overall risk score of 44.73%, while Imo records staffing adequacy of 44.66%. Lagos has a comparatively favourable profile in the selected results, with an overall risk score of 21.33% and staffing adequacy of 91.76%.

- **Different facilities face different risks:** The facilities with the highest overall risk are not necessarily those with the highest service risk. Examining the individual risk components is therefore essential for understanding the type of support each facility may need.

These findings demonstrate the value of combining operational, inventory, staffing, infrastructure, and service-readiness indicators rather than assessing PHC vulnerability through a single measure.

Note: For a detailed breakdown of the analysis, metric derivations, methodology, and findings, click [full project documentation](<report/Team xyz Project Report.pdf>).

## Conclusion

This project demonstrates how Microsoft Fabric and Power BI can be used to develop a risk-based analytics framework for Nigerian Primary Health Care centres. By combining facility-level indicators into an Overall PHC Risk Score, the framework supports the classification of facilities by risk and the investigation of vulnerabilities across states, Local Government Areas (LGAs), and individual facilities.

The analysis highlights multiple dimensions of potential vulnerability, including limited operational functionality, staffing gaps, infrastructure constraints, and widespread medicine and vaccine shortages. These challenges require different responses, making it important to examine the underlying indicators alongside the overall risk classification.

The framework provides a foundation for identifying facilities that warrant further assessment, supporting more targeted resource allocation, and monitoring operational indicators over time.

**Data note:** The project uses synthetic data informed by published research. The figures presented describe the project dataset and should not be interpreted as verified statistics for actual PHC facilities in Nigeria. The inventory analysis also represents a single reporting snapshot and does not establish trends over time.

## Recommendations

Based on the findings, the framework suggests several actions that health authorities, PHC managers, and supply-chain decision-makers could consider:

1. **Prioritise high-risk facilities:** Begin with the 7,237 facilities classified as high risk, validating their individual conditions before determining the appropriate interventions. Monitor medium-risk facilities to identify emerging vulnerabilities.

2. **Investigate vaccine supply gaps:** Examine shortages involving Meningitis A, HPV, Yellow Fever, IPV, and PCV. Verify whether the gaps relate to replenishment delays, distribution challenges, demand patterns, or incomplete reporting.

3. **Address staffing and infrastructure deficiencies:** Assess staffing by professional role and investigate facilities with reported gaps in water, electricity, or storage facilities. Direct interventions towards verified needs rather than relying solely on aggregate scores.

4. **Investigate geographical differences:** Examine the factors contributing to higher risk in areas such as Ondo and Imo, and explore whether effective practices in better-performing areas could be adapted elsewhere.

5. **Strengthen inventory and facility reporting:** Improve the consistency and completeness of facility-level reporting. Track the percentage of facilities experiencing shortages separately from inventory-record shortage rates, and distinguish missing information from confirmed stock availability.

6. **Validate the risk model before operational use:** Confirm the accuracy of facility counts, denominator definitions, missing values, and risk-score calculations. Test the framework against reliable, real-world facility records before using its rankings to guide resource allocation.

7. **Monitor outcomes over time:** Refresh the data periodically and compare successive reporting periods to evaluate changes in stock availability, staffing adequacy, infrastructure access, and service readiness.

Ultimately, the framework illustrates how analytics can help transform facility-level data into actionable risk indicators, enabling stakeholders to investigate potential service gaps, prioritize interventions, and monitor progress towards improved PHC readiness.

