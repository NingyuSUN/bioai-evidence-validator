# Audit packet: single-cell annotations for research summaries

For each record, decide from the cluster's markers:

- `mapping_label`: is the claimed cell type right for this cluster? `correct`, `incorrect` or `uncertain`. A correct but coarser type is `correct`.
- `admission_label`: should the record be admitted for a research summary as it stands? `admitted`, `review_required` or `rejected`.

Write both, with a short rationale, your reviewer id and qualification, the time and `minutes_spent`, in `audit_sheet.csv`. Records are in random order; their route, model and the authors' label are withheld.

## 1. `sc-ba0d303f9838`

- Cluster `c08` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CCL2 (2.8; 90% vs 26%), RGS5 (2.6; 93% vs 8%), C11orf96 (2.5; 98% vs 15%), IGFBP5 (2.5; 98% vs 35%), IFI27 (2.4; 100% vs 31%), TM4SF1 (2.4; 100% vs 28%), JUNB (2.3; 100% vs 64%), TMSB4X (2.3; 100% vs 75%), SOCS3 (2.2; 98% vs 37%), CEBPD (2.1; 98% vs 51%), IGFBP7 (2.1; 100% vs 68%), HSPA1A (2.0; 98% vs 68%), TIMP3 (1.9; 98% vs 40%), MT1A (1.9; 85% vs 16%), DNAJB1 (1.9; 98% vs 62%), CDKN1A (1.9; 98% vs 46%), IRF1 (1.8; 95% vs 37%), NEAT1 (1.8; 100% vs 70%), JUN (1.8; 100% vs 58%), APOLD1 (1.7; 93% vs 15%)
- **Claim:** CL:0000669 *pericyte*
- Cited markers: RGS5 (supports), IGFBP5 (supports), IGFBP7 (supports), TM4SF1 (supports), TIMP3 (supports)

## 2. `sc-2138b2030213`

- Cluster `c06` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): PPY (6.4; 100% vs 54%), SCG2 (2.0; 100% vs 90%), PEG10 (2.0; 100% vs 88%), ID2 (1.8; 98% vs 73%), PAX6 (1.7; 100% vs 79%), ETV1 (1.6; 99% vs 41%), AQP3 (1.6; 90% vs 46%), MEIS2 (1.5; 98% vs 75%), ITM2C (1.3; 99% vs 92%), PCSK2 (1.2; 100% vs 94%), CHGB (1.2; 100% vs 93%), THSD7A (1.2; 86% vs 14%), PAM (1.2; 100% vs 94%), GAD2 (1.2; 98% vs 70%), NEUROD1 (1.2; 99% vs 80%), SERTM1 (1.1; 84% vs 9%), ABCC9 (1.1; 96% vs 71%), UCHL1 (1.1; 97% vs 72%), ABCC8 (1.1; 99% vs 73%), SLC6A4 (1.1; 91% vs 56%)
- **Claim:** CL:0002275 *pancreatic PP cell*
- Cited markers: PPY (supports), PAX6 (supports), PCSK2 (supports), SCG2 (supports), CHGB (supports), PAM (supports), NEUROD1 (supports), SERTM1 (supports)

## 3. `sc-8d801d5b870e`

- Cluster `c13` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): DEFB1 (3.3; 100% vs 38%), SLC12A3 (3.2; 98% vs 4%), TMEM52B (2.7; 100% vs 13%), KNG1 (2.4; 99% vs 16%), MT-ND1 (2.3; 100% vs 94%), WNK1 (2.1; 98% vs 28%), ATP1B1 (2.0; 100% vs 59%), SPP1 (2.0; 98% vs 57%), MT-CO1 (2.0; 100% vs 99%), MT-ND2 (1.9; 100% vs 97%), MT-CO3 (1.9; 100% vs 99%), MT-ATP6 (1.8; 100% vs 97%), MT-ND4 (1.8; 100% vs 97%), MT-CYB (1.8; 100% vs 96%), CA12 (1.7; 98% vs 30%), MALAT1 (1.7; 100% vs 84%), MT-CO2 (1.7; 100% vs 98%), MT-ND5 (1.7; 100% vs 87%), ATP1A1 (1.6; 99% vs 55%), MT-ND3 (1.6; 100% vs 97%)
- **Claim:** CL:1000849 *kidney distal convoluted tubule epithelial cell*
- Cited markers: SLC12A3 (supports), DEFB1 (supports), TMEM52B (supports), KNG1 (supports), WNK1 (supports), CA12 (supports), ATP1B1 (supports), ATP1A1 (supports)

## 4. `sc-2c1b4befc878`

- Cluster `c08` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CXCL14 (4.5; 90% vs 7%), ADAMDEC1 (4.4; 90% vs 7%), LUM (3.7; 90% vs 4%), DCN (3.7; 90% vs 4%), IGFBP7 (3.7; 99% vs 4%), CFD (3.5; 90% vs 11%), GPX3 (3.3; 94% vs 3%), RARRES2 (3.0; 91% vs 4%), APOE (2.9; 84% vs 5%), IFITM3 (2.8; 100% vs 25%), CALD1 (2.8; 99% vs 3%), VIM (2.6; 100% vs 34%), COL3A1 (2.6; 90% vs 3%), TCF21 (2.4; 90% vs 1%), COL1A2 (2.4; 90% vs 2%), CXCL6 (2.3; 88% vs 1%), MFAP4 (2.3; 89% vs 1%), C1S (2.1; 89% vs 1%), ADH1B (2.1; 90% vs 9%), CTSC (2.1; 88% vs 32%)
- **Claim:** CL:0000057 *fibroblast*
- Cited markers: CXCL14 (supports), LUM (supports), DCN (supports), CFD (supports), RARRES2 (supports), CALD1 (supports), COL3A1 (supports), TCF21 (supports), COL1A2 (supports), MFAP4 (supports), C1S (supports), ADAMDEC1 (supports)

## 5. `sc-2eff7bb75fad`

- Cluster `c02` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): HBB (7.7; 100% vs 31%), HBA1 (7.0; 100% vs 14%), HBA2 (6.8; 100% vs 18%), HBD (4.2; 92% vs 3%), AHSP (3.2; 98% vs 2%), CA1 (3.0; 91% vs 2%), SLC25A37 (2.9; 96% vs 13%), HBM (2.8; 89% vs 1%), ALAS2 (2.4; 96% vs 1%), SLC4A1 (1.9; 85% vs 1%), BLVRB (1.8; 92% vs 43%), SNCA (1.8; 91% vs 2%), GYPA (1.7; 79% vs 0%), SLC25A39 (1.6; 91% vs 17%), BNIP3L (1.6; 89% vs 18%), BSG (1.5; 94% vs 29%), YBX3 (1.5; 87% vs 16%), GLRX5 (1.4; 87% vs 22%), GYPC (1.4; 92% vs 25%), HMBS (1.4; 81% vs 6%)
- **Claim:** CL:0000232 *erythrocyte*
- Cited markers: HBB (supports), HBA1 (supports), HBA2 (supports), HBD (supports), AHSP (supports), CA1 (supports), SLC25A37 (supports), HBM (supports), ALAS2 (supports), SLC4A1 (supports), BLVRB (supports), SNCA (supports), GYPA (supports), SLC25A39 (supports), BNIP3L (supports), BSG (supports), YBX3 (supports), GLRX5 (supports), GYPC (supports), HMBS (supports)

## 6. `sc-47865daed309`

- Cluster `c03` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): JCHAIN (5.6; 100% vs 99%), IGLL5 (3.0; 100% vs 89%), MZB1 (3.0; 100% vs 19%), SSR4 (2.7; 100% vs 90%), DERL3 (2.6; 99% vs 15%), HERPUD1 (2.3; 100% vs 66%), FKBP11 (2.3; 99% vs 34%), CD79A (2.2; 98% vs 6%), XBP1 (2.2; 99% vs 74%), TNFRSF17 (2.1; 98% vs 6%), SEC11C (2.0; 99% vs 57%), SPCS2 (1.9; 100% vs 72%), DNAJB9 (1.8; 96% vs 30%), ITM2C (1.8; 92% vs 25%), CYBA (1.8; 100% vs 82%), UBE2J1 (1.7; 99% vs 54%), SRGN (1.7; 96% vs 15%), LGALS1 (1.6; 94% vs 17%), JUN (1.6; 99% vs 94%), SPCS1 (1.5; 100% vs 79%)
- **Claim:** CL:0000786 *plasma cell*
- Cited markers: MZB1 (supports), TNFRSF17 (supports), JCHAIN (supports), XBP1 (supports), DERL3 (supports), FKBP11 (supports), CD79A (supports), IGLL5 (supports)

## 7. `sc-43489d3f91fb`

- Cluster `c09` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): WFDC2 (2.9; 97% vs 21%), KRT7 (2.8; 100% vs 13%), IGFBP5 (2.0; 97% vs 35%), CA12 (1.9; 97% vs 33%), TMEM213 (1.9; 97% vs 21%), CD9 (1.8; 100% vs 50%), ATP6V1G3 (1.8; 90% vs 10%), MALAT1 (1.8; 100% vs 85%), ATP6V0B (1.7; 100% vs 52%), LGALS3 (1.7; 100% vs 39%), ATP6V0D2 (1.6; 94% vs 13%), TSPAN8 (1.6; 87% vs 8%), ATP6V1B1 (1.6; 94% vs 20%), KRT8 (1.4; 94% vs 38%), HEPACAM2 (1.4; 90% vs 8%), ATP6AP2 (1.4; 97% vs 44%), S100A2 (1.3; 81% vs 23%), ID3 (1.3; 87% vs 33%), IL18 (1.3; 90% vs 12%), SLC26A4 (1.3; 77% vs 1%)
- **Claim:** CL:0002306 *epithelial cell of proximal tubule*
- Cited markers: WFDC2 (supports), KRT7 (supports), KRT8 (supports), CA12 (supports), SLC26A4 (supports), ATP6V1G3 (supports), ATP6V0B (supports), ATP6V0D2 (supports), ATP6V1B1 (supports), ATP6AP2 (supports), IGFBP5 (supports), TSPAN8 (supports), HEPACAM2 (supports)

## 8. `sc-457686ee8397`

- Cluster `c07` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CCL21 (4.2; 97% vs 20%), TFF3 (3.6; 100% vs 8%), CLDN5 (2.2; 92% vs 13%), TFPI (2.0; 94% vs 19%), GNG11 (1.9; 93% vs 30%), MMRN1 (1.8; 85% vs 2%), IGFBP7 (1.7; 99% vs 65%), TM4SF1 (1.6; 91% vs 35%), ADIRF (1.6; 99% vs 74%), SNCG (1.5; 79% vs 13%), ECSCR (1.4; 79% vs 10%), RAMP2 (1.4; 81% vs 17%), FABP4 (1.3; 65% vs 5%), PROX1 (1.3; 72% vs 3%), HLA-E (1.3; 95% vs 62%), LYVE1 (1.3; 67% vs 1%), PPFIBP1 (1.2; 72% vs 10%), SOX4 (1.2; 74% vs 34%), CAVIN2 (1.2; 68% vs 4%), ARL4A (1.1; 78% vs 28%)
- **Claim:** CL:0002138 *endothelial cell of lymphatic vessel*
- Cited markers: CCL21 (supports), TFF3 (supports), PROX1 (supports), LYVE1 (supports), MMRN1 (supports), CLDN5 (supports), TFPI (supports), GNG11 (supports), ECSCR (supports), RAMP2 (supports), CAVIN2 (supports), PPFIBP1 (supports), SNCG (supports), TM4SF1 (supports), FABP4 (supports)

## 9. `sc-1bb81802ec74`

- Cluster `c08` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): TM4SF1 (3.0; 98% vs 29%), IFI27 (2.6; 98% vs 29%), SELE (2.1; 72% vs 10%), ACKR1 (2.1; 81% vs 14%), SPARCL1 (2.0; 91% vs 20%), CD74 (1.9; 99% vs 61%), TSC22D1 (1.9; 90% vs 40%), SPRY1 (1.7; 81% vs 20%), AQP1 (1.5; 86% vs 28%), SAT1 (1.5; 97% vs 78%), HLA-E (1.4; 94% vs 60%), ADIRF (1.4; 98% vs 72%), IFITM3 (1.4; 98% vs 66%), GNG11 (1.4; 81% vs 26%), RCAN1 (1.3; 71% vs 17%), SOCS3 (1.3; 83% vs 41%), PCAT19 (1.3; 73% vs 5%), CLDN5 (1.3; 69% vs 9%), RAMP2 (1.2; 72% vs 13%), MCTP1 (1.2; 70% vs 6%)
- **Claim:** CL:0002543 *vein endothelial cell*
- Cited markers: ACKR1 (supports), SELE (supports), CLDN5 (supports), RAMP2 (supports), GNG11 (supports), AQP1 (supports), SPARCL1 (supports), TM4SF1 (supports)

## 10. `sc-01ab2950a674`

- Cluster `c07` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): GNLY (2.0; 57% vs 7%), NKG7 (1.8; 65% vs 23%), TMSB10 (1.3; 97% vs 76%), IGKC (1.2; 60% vs 34%), GZMB (1.2; 53% vs 4%), TUBA1B (1.2; 63% vs 31%), TMSB4X (1.2; 98% vs 89%), PTMA (1.1; 99% vs 91%), MALAT1 (1.1; 99% vs 97%), CORO1A (1.1; 75% vs 29%), CCL5 (1.1; 54% vs 20%), FGFBP2 (1.0; 45% vs 2%), KLRD1 (1.0; 55% vs 14%), PFN1 (1.0; 95% vs 79%), H4C3 (1.0; 64% vs 48%), HMGB2 (1.0; 57% vs 23%), HMGN2 (1.0; 69% vs 40%), CYBA (1.0; 84% vs 44%), CCL4 (1.0; 57% vs 22%), HLA-B (1.0; 96% vs 86%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: GNLY (supports), NKG7 (supports), IGKC (contradicts), GZMB (supports), CCL5 (supports), FGFBP2 (supports), KLRD1 (supports), CCL4 (supports)

## 11. `sc-9bd026197028`

- Cluster `c11` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): FXYD4 (2.8; 83% vs 8%), AQP2 (2.7; 80% vs 4%), AQP3 (2.1; 80% vs 12%), MALAT1 (2.1; 100% vs 84%), MT-CO1 (1.6; 100% vs 99%), CLU (1.6; 84% vs 39%), WFDC2 (1.6; 78% vs 20%), TACSTD2 (1.6; 78% vs 21%), GDF15 (1.5; 80% vs 29%), MT-CO2 (1.4; 100% vs 98%), S100A6 (1.4; 92% vs 67%), MT-CO3 (1.4; 100% vs 99%), CDH16 (1.3; 86% vs 32%), KRT19 (1.3; 68% vs 10%), MT-ND4 (1.3; 100% vs 98%), KRT18 (1.3; 83% vs 38%), MT-CYB (1.3; 100% vs 97%), ELF3 (1.2; 76% vs 25%), MT-ATP6 (1.2; 100% vs 97%), NEAT1 (1.2; 97% vs 69%)
- **Claim:** CL:1001431 *kidney collecting duct principal cell*
- Cited markers: AQP2 (supports), AQP3 (supports), FXYD4 (supports), CDH16 (supports), KRT18 (supports), KRT19 (supports), TACSTD2 (supports), WFDC2 (supports)

## 12. `sc-66d221735c3f`

- Cluster `c03` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): C1QA (3.6; 100% vs 14%), C1QB (3.5; 99% vs 11%), CD163 (2.9; 99% vs 10%), HLA-DRA (2.7; 98% vs 22%), CTSB (2.6; 99% vs 38%), MARCO (2.6; 86% vs 4%), FTL (2.5; 100% vs 100%), SLC40A1 (2.5; 94% vs 32%), C1QC (2.5; 95% vs 8%), MS4A6A (2.4; 95% vs 17%), CD74 (2.3; 98% vs 40%), MS4A7 (2.3; 91% vs 8%), CTSS (2.3; 96% vs 24%), AIF1 (2.2; 95% vs 15%), TYROBP (2.2; 97% vs 28%), NPC2 (2.2; 97% vs 42%), SAT1 (2.2; 100% vs 72%), GPX1 (2.1; 99% vs 66%), HMOX1 (2.1; 85% vs 9%), FCER1G (2.1; 94% vs 24%)
- **Claim:** CL:0000091 *Kupffer cell*
- Cited markers: C1QA (supports), C1QB (supports), C1QC (supports), CD163 (supports), MARCO (supports), CD74 (supports), HLA-DRA (supports), MS4A6A (supports), MS4A7 (supports), AIF1 (supports), CTSB (supports), CTSS (supports), TYROBP (supports), FCER1G (supports), HMOX1 (supports)

## 13. `sc-81eace82fee7`

- Cluster `c05` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): LYZ (2.9; 98% vs 25%), MT1G (2.4; 98% vs 77%), GUCA2B (2.2; 61% vs 25%), BEST4 (2.2; 74% vs 1%), SPIB (2.0; 84% vs 4%), MT2A (1.9; 96% vs 82%), MT1E (1.8; 99% vs 70%), MT1H (1.8; 82% vs 52%), CFTR (1.7; 92% vs 28%), MT1X (1.6; 96% vs 60%), GSN (1.5; 82% vs 34%), CPA2 (1.4; 75% vs 3%), CA7 (1.4; 68% vs 1%), KRT20 (1.4; 83% vs 44%), CTSE (1.2; 90% vs 29%), GUCA2A (1.2; 50% vs 2%), FXYD3 (1.2; 94% vs 49%), S100A6 (1.2; 100% vs 95%), MT1M (1.1; 74% vs 27%), STARD10 (1.1; 94% vs 32%)
- **Claim:** CL:0000584 *enterocyte*
- Cited markers: BEST4 (supports), SPIB (supports), CFTR (supports), CA7 (supports), CPA2 (supports), GUCA2B (supports), GUCA2A (supports), LYZ (supports)

## 14. `sc-c218ebe7c140`

- Cluster `c05` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): TAGLN (3.7; 95% vs 8%), MYL9 (3.1; 97% vs 16%), RGS5 (3.1; 84% vs 6%), ACTA2 (2.9; 89% vs 5%), TPM2 (2.8; 94% vs 8%), CALD1 (2.8; 99% vs 34%), ADIRF (2.7; 95% vs 56%), C11orf96 (2.6; 93% vs 13%), MGP (2.4; 96% vs 20%), LGALS1 (2.3; 97% vs 33%), IGFBP7 (2.3; 97% vs 68%), VIM (2.2; 94% vs 34%), MALAT1 (2.1; 100% vs 84%), SPARCL1 (2.1; 87% vs 13%), MYH11 (1.9; 72% vs 2%), JUNB (1.9; 94% vs 63%), BGN (1.9; 84% vs 5%), SOD3 (1.8; 81% vs 19%), FLNA (1.8; 86% vs 24%), MT2A (1.7; 99% vs 90%)
- **Claim:** CL:0000192 *smooth muscle cell*
- Cited markers: TAGLN (supports), MYL9 (supports), RGS5 (supports), ACTA2 (supports), TPM2 (supports), CALD1 (supports), MYH11 (supports)

## 15. `sc-4937458f58f8`

- Cluster `c08` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): S100A9 (2.9; 89% vs 13%), TYROBP (2.7; 99% vs 23%), LYZ (2.7; 90% vs 8%), S100A8 (2.4; 68% vs 11%), AIF1 (2.3; 92% vs 10%), HLA-DRA (2.2; 86% vs 18%), S100A6 (2.1; 87% vs 31%), CTSS (2.1; 92% vs 20%), CD74 (2.1; 92% vs 37%), S100A4 (2.1; 86% vs 28%), TMSB10 (2.0; 100% vs 75%), FCER1G (1.9; 92% vs 19%), VIM (1.9; 92% vs 33%), GPX1 (1.9; 98% vs 64%), C1QA (1.8; 63% vs 12%), SAT1 (1.8; 97% vs 71%), S100A11 (1.8; 90% vs 23%), LST1 (1.7; 83% vs 8%), CST3 (1.7; 98% vs 63%), TMSB4X (1.7; 100% vs 88%)
- **Claim:** CL:0000235 *macrophage*
- Cited markers: S100A9 (supports), TYROBP (supports), LYZ (supports), S100A8 (supports), AIF1 (supports), HLA-DRA (supports), CTSS (supports), CD74 (supports), C1QA (supports)

## 16. `sc-f6b33d5ab782`

- Cluster `c05` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): KRT1 (3.3; 97% vs 30%), DMKN (3.2; 98% vs 32%), KRT10 (3.1; 98% vs 49%), SFN (3.1; 98% vs 45%), LGALS7B (2.9; 97% vs 14%), PERP (2.7; 98% vs 42%), KRTDAP (2.7; 89% vs 12%), LY6D (2.6; 96% vs 23%), S100A14 (2.5; 98% vs 29%), LYPD3 (2.1; 91% vs 18%), AQP3 (2.1; 94% vs 24%), DSP (2.1; 94% vs 19%), TACSTD2 (1.7; 91% vs 24%), SERPINB5 (1.7; 90% vs 16%), KRT14 (1.6; 95% vs 67%), CCL27 (1.5; 86% vs 12%), RNF144B (1.5; 79% vs 19%), MIR205HG (1.4; 88% vs 21%), CLDN1 (1.4; 81% vs 11%), FXYD3 (1.4; 86% vs 17%)
- **Claim:** CL:0000312 *keratinocyte*
- Cited markers: KRT1 (supports), KRT10 (supports), KRTDAP (supports), DMKN (supports), SFN (supports), LGALS7B (supports), PERP (supports), LY6D (supports), S100A14 (supports), DSP (supports), KRT14 (supports), CCL27 (supports), AQP3 (supports), SERPINB5 (supports), MIR205HG (supports), CLDN1 (supports)

## 17. `sc-7c5b8a9c5536`

- Cluster `c03` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): HBB (7.2; 91% vs 27%), HBA2 (6.2; 89% vs 12%), HBA1 (5.5; 87% vs 5%), HBD (2.2; 79% vs 0%), SLC25A37 (1.0; 60% vs 25%), SLC25A39 (1.0; 53% vs 11%), HBM (0.6; 28% vs 0%), GYPC (0.6; 49% vs 26%), FBXO7 (0.6; 37% vs 14%), FKBP8 (0.4; 46% vs 33%), SNCA (0.4; 25% vs 8%), UBBP4 (0.1; 28% vs 28%)
- **Claim:** CL:0000232 *erythrocyte*
- Cited markers: HBB (supports), HBA2 (supports), HBA1 (supports), HBD (supports), HBM (supports), SLC25A37 (supports), SLC25A39 (supports), GYPC (supports), FBXO7 (supports), SNCA (supports)

## 18. `sc-dc6252fb95cb`

- Cluster `c12` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): TMEM213 (2.3; 98% vs 16%), SLC4A1 (2.0; 96% vs 4%), SPINK1 (1.9; 72% vs 4%), ATP6V0D2 (1.9; 98% vs 8%), ATP6V1G3 (1.9; 96% vs 4%), ATP6AP2 (1.8; 98% vs 41%), ADGRF5 (1.8; 96% vs 20%), C12orf75 (1.7; 97% vs 36%), LGALS3 (1.7; 96% vs 35%), SLC26A7 (1.7; 95% vs 4%), MT-CO1 (1.6; 100% vs 99%), ATP6V0B (1.6; 97% vs 49%), RHCG (1.6; 92% vs 9%), MALAT1 (1.6; 100% vs 84%), ATP6V1B1 (1.6; 96% vs 15%), BSG (1.6; 99% vs 55%), MT-ND1 (1.6; 100% vs 94%), CKB (1.6; 96% vs 34%), MT-CO3 (1.5; 100% vs 99%), CA12 (1.5; 98% vs 28%)
- **Claim:** CL:0005011 *renal alpha-intercalated cell*
- Cited markers: SLC4A1 (supports), SLC26A7 (supports), ATP6V0D2 (supports), ATP6V1G3 (supports), ATP6AP2 (supports), ATP6V0B (supports), ATP6V1B1 (supports), RHCG (supports), CA12 (supports)

## 19. `sc-fef6c4941874`

- Cluster `c04` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CD74 (2.3; 100% vs 62%), CXCR4 (2.2; 85% vs 16%), CD52 (2.1; 85% vs 7%), IGKC (2.0; 59% vs 4%), MALAT1 (2.0; 100% vs 85%), RPS29 (1.9; 100% vs 97%), RPS27 (1.9; 100% vs 99%), HLA-DRA (1.9; 91% vs 43%), RPS2 (1.7; 100% vs 91%), RPLP2 (1.7; 100% vs 98%), RPS21 (1.6; 97% vs 89%), RPS8 (1.6; 100% vs 95%), RPS15A (1.6; 100% vs 96%), RPL18A (1.5; 100% vs 96%), RPS19 (1.5; 100% vs 96%), CD79A (1.5; 59% vs 0%), LTB (1.5; 62% vs 4%), TMSB4X (1.5; 97% vs 75%), RPS10 (1.5; 94% vs 76%), NBEAL1 (1.5; 85% vs 58%)
- **Claim:** CL:0000236 *B cell*
- Cited markers: CD79A (supports), IGKC (supports), CD74 (supports), HLA-DRA (supports), CD52 (supports), CXCR4 (supports), LTB (supports)

## 20. `sc-ae30f1136126`

- Cluster `c12` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (2.2; 99% vs 57%), IL7R (2.1; 98% vs 35%), IL4I1 (1.6; 84% vs 5%), LST1 (1.5; 86% vs 17%), CCR6 (1.4; 86% vs 4%), VIM (1.4; 96% vs 66%), S100A4 (1.4; 92% vs 62%), RORC (1.4; 82% vs 6%), S100A6 (1.4; 89% vs 44%), TNFAIP3 (1.3; 96% vs 60%), AQP3 (1.3; 88% vs 30%), RGS1 (1.2; 92% vs 54%), ITM2C (1.1; 85% vs 34%), JAML (1.0; 76% vs 17%), DDIT4 (1.0; 90% vs 60%), CXCR4 (1.0; 86% vs 50%), KIT (1.0; 66% vs 4%), TMIGD2 (0.9; 84% vs 46%), IL23R (0.9; 70% vs 8%), ZFP36L1 (0.9; 98% vs 88%)
- **Claim:** CL:0000899 *T-helper 17 cell*
- Cited markers: RORC (supports), CCR6 (supports), IL23R (supports), IL7R (supports), LTB (supports), LST1 (supports), TNFAIP3 (supports), RGS1 (supports), ITM2C (supports), JAML (supports)

## 21. `sc-3440a71c316e`

- Cluster `c04` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (1.7; 97% vs 56%), IL32 (1.7; 98% vs 61%), CD52 (1.3; 97% vs 67%), CD27 (1.3; 88% vs 36%), S100A4 (1.1; 88% vs 61%), CD2 (1.0; 84% vs 34%), FOXP3 (1.0; 59% vs 0%), ID3 (1.0; 76% vs 31%), CD3E (1.0; 98% vs 66%), CTLA4 (1.0; 61% vs 1%), SELL (1.0; 78% vs 34%), TNFRSF1B (1.0; 75% vs 25%), PIM2 (0.9; 80% vs 37%), SIRPG (0.9; 72% vs 21%), FXYD5 (0.9; 92% vs 68%), TRAC (0.8; 81% vs 38%), DGKA (0.8; 75% vs 31%), ITM2A (0.8; 79% vs 44%), CD5 (0.7; 67% vs 20%), LEF1 (0.7; 72% vs 35%)
- **Claim:** CL:0000815 *regulatory T cell*
- Cited markers: FOXP3 (supports), CTLA4 (supports), CD27 (supports), CD3E (supports), TRAC (supports), CD2 (supports), CD52 (supports), SELL (supports), LEF1 (supports), IL32 (supports)

## 22. `sc-bffa8ceffd0e`

- Cluster `c10` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): NKG7 (2.1; 100% vs 67%), GNLY (2.0; 80% vs 23%), GZMB (1.9; 94% vs 23%), SPON2 (1.8; 92% vs 21%), FCGR3A (1.7; 94% vs 26%), PRF1 (1.7; 99% vs 54%), FGFBP2 (1.6; 85% vs 14%), GZMH (1.6; 88% vs 23%), CST7 (1.6; 99% vs 53%), CCL5 (1.6; 88% vs 47%), CLIC3 (1.5; 96% vs 47%), TYROBP (1.5; 99% vs 50%), FCER1G (1.4; 99% vs 57%), CCL4 (1.4; 95% vs 48%), GZMA (1.3; 100% vs 65%), ADGRG1 (1.3; 85% vs 22%), CX3CR1 (1.3; 80% vs 14%), TBX21 (1.3; 86% vs 29%), CTSW (1.2; 99% vs 72%), MYOM2 (1.2; 58% vs 11%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: NKG7 (supports), GNLY (supports), GZMB (supports), PRF1 (supports), FGFBP2 (supports), GZMH (supports), FCGR3A (supports), TYROBP (supports), FCER1G (supports), CX3CR1 (supports), TBX21 (supports), CCL5 (supports)

## 23. `sc-b855c9140617`

- Cluster `c07` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): GNLY (2.0; 57% vs 7%), NKG7 (1.8; 65% vs 23%), TMSB10 (1.3; 97% vs 76%), IGKC (1.2; 60% vs 34%), GZMB (1.2; 53% vs 4%), TUBA1B (1.2; 63% vs 31%), TMSB4X (1.2; 98% vs 89%), PTMA (1.1; 99% vs 91%), MALAT1 (1.1; 99% vs 97%), CORO1A (1.1; 75% vs 29%), CCL5 (1.1; 54% vs 20%), FGFBP2 (1.0; 45% vs 2%), KLRD1 (1.0; 55% vs 14%), PFN1 (1.0; 95% vs 79%), H4C3 (1.0; 64% vs 48%), HMGB2 (1.0; 57% vs 23%), HMGN2 (1.0; 69% vs 40%), CYBA (1.0; 84% vs 44%), CCL4 (1.0; 57% vs 22%), HLA-B (1.0; 96% vs 86%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: GNLY (supports), NKG7 (supports), GZMB (supports), FGFBP2 (supports), KLRD1 (supports), CCL5 (supports), CCL4 (supports), CORO1A (supports), IGKC (contradicts)

## 24. `sc-00a40a840007`

- Cluster `c07` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (1.3; 97% vs 57%), CXCR4 (1.3; 89% vs 50%), IL32 (1.3; 93% vs 62%), GZMK (1.2; 77% vs 28%), IL7R (1.1; 85% vs 36%), TRDV2 (1.1; 44% vs 4%), S100A4 (1.1; 91% vs 62%), TNFAIP3 (1.0; 86% vs 60%), DUSP2 (0.9; 93% vs 80%), SPOCK2 (0.9; 86% vs 44%), KLRB1 (0.9; 94% vs 73%), NFKBIA (0.9; 94% vs 81%), TC2N (0.9; 74% vs 28%), S100A6 (0.9; 81% vs 45%), CD3E (0.9; 92% vs 67%), IL23R (0.8; 57% vs 9%), CD69 (0.8; 98% vs 92%), FOSB (0.7; 90% vs 74%), DUSP1 (0.7; 99% vs 93%), SLC4A10 (0.7; 50% vs 5%)
- **Claim:** CL:0000940 *mucosal invariant T cell*
- Cited markers: SLC4A10 (supports), KLRB1 (supports), IL23R (supports), GZMK (supports), IL7R (supports), CD3E (supports), LTB (supports), CXCR4 (supports), IL32 (supports), S100A4 (supports), CD69 (supports), TRDV2 (contradicts)

## 25. `sc-4d6f03e0ceaf`

- Cluster `c08` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CCL2 (2.8; 90% vs 26%), RGS5 (2.6; 93% vs 8%), C11orf96 (2.5; 98% vs 15%), IGFBP5 (2.5; 98% vs 35%), IFI27 (2.4; 100% vs 31%), TM4SF1 (2.4; 100% vs 28%), JUNB (2.3; 100% vs 64%), TMSB4X (2.3; 100% vs 75%), SOCS3 (2.2; 98% vs 37%), CEBPD (2.1; 98% vs 51%), IGFBP7 (2.1; 100% vs 68%), HSPA1A (2.0; 98% vs 68%), TIMP3 (1.9; 98% vs 40%), MT1A (1.9; 85% vs 16%), DNAJB1 (1.9; 98% vs 62%), CDKN1A (1.9; 98% vs 46%), IRF1 (1.8; 95% vs 37%), NEAT1 (1.8; 100% vs 70%), JUN (1.8; 100% vs 58%), APOLD1 (1.7; 93% vs 15%)
- **Claim:** CL:0000669 *pericyte*
- Cited markers: RGS5 (supports), IGFBP5 (supports), IGFBP7 (supports), TIMP3 (supports)

## 26. `sc-c09fd2a58e63`

- Cluster `c05` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): TAGLN (3.7; 95% vs 8%), MYL9 (3.1; 97% vs 16%), RGS5 (3.1; 84% vs 6%), ACTA2 (2.9; 89% vs 5%), TPM2 (2.8; 94% vs 8%), CALD1 (2.8; 99% vs 34%), ADIRF (2.7; 95% vs 56%), C11orf96 (2.6; 93% vs 13%), MGP (2.4; 96% vs 20%), LGALS1 (2.3; 97% vs 33%), IGFBP7 (2.3; 97% vs 68%), VIM (2.2; 94% vs 34%), MALAT1 (2.1; 100% vs 84%), SPARCL1 (2.1; 87% vs 13%), MYH11 (1.9; 72% vs 2%), JUNB (1.9; 94% vs 63%), BGN (1.9; 84% vs 5%), SOD3 (1.8; 81% vs 19%), FLNA (1.8; 86% vs 24%), MT2A (1.7; 99% vs 90%)
- **Claim:** CL:0000359 *vascular smooth muscle cell*
- Cited markers: ACTA2 (supports), MYH11 (supports), TAGLN (supports), MYL9 (supports), TPM2 (supports), CALD1 (supports), RGS5 (supports), MGP (supports), SPARCL1 (supports), BGN (supports), SOD3 (supports)

## 27. `sc-7c94fc7a0196`

- Cluster `c07` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): GNLY (4.0; 95% vs 2%), NKG7 (3.7; 96% vs 2%), GZMB (2.6; 84% vs 2%), CCL5 (2.4; 80% vs 4%), CCL4 (2.4; 77% vs 14%), TMSB4X (2.2; 100% vs 74%), MALAT1 (2.1; 100% vs 84%), CST7 (2.1; 79% vs 2%), B2M (1.8; 100% vs 96%), AREG (1.7; 64% vs 15%), HLA-C (1.7; 96% vs 71%), TMSB10 (1.7; 100% vs 88%), FGFBP2 (1.6; 62% vs 0%), SRGN (1.6; 80% vs 33%), KLRD1 (1.6; 59% vs 2%), CREM (1.5; 72% vs 36%), HLA-A (1.5; 99% vs 77%), HCST (1.5; 66% vs 8%), CYBA (1.5; 86% vs 55%), GZMA (1.5; 59% vs 1%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: GNLY (supports), NKG7 (supports), GZMB (supports), GZMA (supports), CST7 (supports), FGFBP2 (supports), KLRD1 (supports), CCL5 (supports), CCL4 (supports), HCST (supports), SRGN (supports)

## 28. `sc-6cf84b7db7a2`

- Cluster `c03` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): CD8B (1.6; 89% vs 8%), LTB (1.4; 100% vs 55%), LEF1 (1.3; 97% vs 32%), CD52 (1.2; 100% vs 66%), CCR7 (1.2; 90% vs 23%), TCF7 (1.1; 90% vs 33%), CD8A (1.1; 88% vs 29%), SELL (1.1; 86% vs 32%), RGS10 (1.1; 94% vs 35%), LINC02446 (1.1; 63% vs 3%), LDHB (1.0; 99% vs 73%), AIF1 (1.0; 93% vs 35%), NOSIP (1.0; 94% vs 52%), IL7R (1.0; 84% vs 33%), CD3E (1.0; 99% vs 65%), LRRN3 (0.9; 72% vs 13%), CD27 (0.9; 91% vs 34%), RPS8 (0.8; 100% vs 100%), S100B (0.8; 52% vs 12%), RPLP0 (0.8; 100% vs 98%)
- **Claim:** CL:0000900 *naive thymus-derived CD8-positive, alpha-beta T cell*
- Cited markers: CD8B (supports), CD8A (supports), CCR7 (supports), LEF1 (supports), TCF7 (supports), SELL (supports), IL7R (supports), CD27 (supports), CD3E (supports), LTB (supports)

## 29. `sc-92d87108bf26`

- Cluster `c03` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): C1QA (3.6; 100% vs 14%), C1QB (3.5; 99% vs 11%), CD163 (2.9; 99% vs 10%), HLA-DRA (2.7; 98% vs 22%), CTSB (2.6; 99% vs 38%), MARCO (2.6; 86% vs 4%), FTL (2.5; 100% vs 100%), SLC40A1 (2.5; 94% vs 32%), C1QC (2.5; 95% vs 8%), MS4A6A (2.4; 95% vs 17%), CD74 (2.3; 98% vs 40%), MS4A7 (2.3; 91% vs 8%), CTSS (2.3; 96% vs 24%), AIF1 (2.2; 95% vs 15%), TYROBP (2.2; 97% vs 28%), NPC2 (2.2; 97% vs 42%), SAT1 (2.2; 100% vs 72%), GPX1 (2.1; 99% vs 66%), HMOX1 (2.1; 85% vs 9%), FCER1G (2.1; 94% vs 24%)
- **Claim:** CL:0000091 *Kupffer cell*
- Cited markers: C1QA (supports), C1QB (supports), C1QC (supports), CD163 (supports), MARCO (supports), SLC40A1 (supports), MS4A6A (supports), MS4A7 (supports), FCER1G (supports), TYROBP (supports), HLA-DRA (supports), CD74 (supports)

## 30. `sc-26e57da30416`

- Cluster `c07` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): TMSB4X (2.9; 100% vs 100%), CD7 (2.7; 92% vs 11%), KLRB1 (2.4; 92% vs 10%), CD52 (2.3; 97% vs 18%), CORO1A (2.1; 96% vs 20%), GZMA (2.0; 59% vs 7%), CD3E (2.0; 97% vs 7%), EVL (1.9; 97% vs 21%), PTPRCAP (1.9; 97% vs 28%), ACTB (1.9; 100% vs 99%), HCST (1.8; 93% vs 12%), ARHGDIB (1.7; 95% vs 23%), NKG7 (1.6; 80% vs 5%), CD247 (1.6; 76% vs 2%), ALOX5AP (1.6; 89% vs 11%), VIM (1.5; 92% vs 34%), COTL1 (1.5; 91% vs 44%), RAC2 (1.5; 87% vs 21%), ACAP1 (1.5; 88% vs 14%), LCK (1.5; 86% vs 5%)
- **Claim:** CL:0000084 *T cell*
- Cited markers: CD3E (supports), CD247 (supports), LCK (supports), CD7 (supports), KLRB1 (supports), GZMA (supports), NKG7 (supports), CD52 (supports), CORO1A (supports), PTPRCAP (supports), HCST (supports), ACAP1 (supports)

## 31. `sc-2258691ddec9`

- Cluster `c06` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): PPY (6.4; 100% vs 54%), SCG2 (2.0; 100% vs 90%), PEG10 (2.0; 100% vs 88%), ID2 (1.8; 98% vs 73%), PAX6 (1.7; 100% vs 79%), ETV1 (1.6; 99% vs 41%), AQP3 (1.6; 90% vs 46%), MEIS2 (1.5; 98% vs 75%), ITM2C (1.3; 99% vs 92%), PCSK2 (1.2; 100% vs 94%), CHGB (1.2; 100% vs 93%), THSD7A (1.2; 86% vs 14%), PAM (1.2; 100% vs 94%), GAD2 (1.2; 98% vs 70%), NEUROD1 (1.2; 99% vs 80%), SERTM1 (1.1; 84% vs 9%), ABCC9 (1.1; 96% vs 71%), UCHL1 (1.1; 97% vs 72%), ABCC8 (1.1; 99% vs 73%), SLC6A4 (1.1; 91% vs 56%)
- **Claim:** CL:0002275 *pancreatic PP cell*
- Cited markers: PPY (supports), PAX6 (supports), NEUROD1 (supports), SCG2 (supports), CHGB (supports), PCSK2 (supports), PAM (supports)

## 32. `sc-00ad508b5979`

- Cluster `c07` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CCL21 (4.2; 97% vs 20%), TFF3 (3.6; 100% vs 8%), CLDN5 (2.2; 92% vs 13%), TFPI (2.0; 94% vs 19%), GNG11 (1.9; 93% vs 30%), MMRN1 (1.8; 85% vs 2%), IGFBP7 (1.7; 99% vs 65%), TM4SF1 (1.6; 91% vs 35%), ADIRF (1.6; 99% vs 74%), SNCG (1.5; 79% vs 13%), ECSCR (1.4; 79% vs 10%), RAMP2 (1.4; 81% vs 17%), FABP4 (1.3; 65% vs 5%), PROX1 (1.3; 72% vs 3%), HLA-E (1.3; 95% vs 62%), LYVE1 (1.3; 67% vs 1%), PPFIBP1 (1.2; 72% vs 10%), SOX4 (1.2; 74% vs 34%), CAVIN2 (1.2; 68% vs 4%), ARL4A (1.1; 78% vs 28%)
- **Claim:** CL:0002138 *lymphatic endothelial cell*
- Cited markers: CCL21 (supports), CLDN5 (supports), MMRN1 (supports), PROX1 (supports), LYVE1 (supports), CAVIN2 (supports), RAMP2 (supports), ECSCR (supports), GNG11 (supports), TFPI (supports), TM4SF1 (supports), FABP4 (supports)

## 33. `sc-a271a8ebacae`

- Cluster `c11` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): FXYD4 (2.8; 83% vs 8%), AQP2 (2.7; 80% vs 4%), AQP3 (2.1; 80% vs 12%), MALAT1 (2.1; 100% vs 84%), MT-CO1 (1.6; 100% vs 99%), CLU (1.6; 84% vs 39%), WFDC2 (1.6; 78% vs 20%), TACSTD2 (1.6; 78% vs 21%), GDF15 (1.5; 80% vs 29%), MT-CO2 (1.4; 100% vs 98%), S100A6 (1.4; 92% vs 67%), MT-CO3 (1.4; 100% vs 99%), CDH16 (1.3; 86% vs 32%), KRT19 (1.3; 68% vs 10%), MT-ND4 (1.3; 100% vs 98%), KRT18 (1.3; 83% vs 38%), MT-CYB (1.3; 100% vs 97%), ELF3 (1.2; 76% vs 25%), MT-ATP6 (1.2; 100% vs 97%), NEAT1 (1.2; 97% vs 69%)
- **Claim:** CL:1001431 *kidney collecting duct principal cell*
- Cited markers: AQP2 (supports), FXYD4 (supports), AQP3 (supports), CDH16 (supports), KRT19 (supports), KRT18 (supports)

## 34. `sc-f0f257d1b718`

- Cluster `c05` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): KRT1 (3.3; 97% vs 30%), DMKN (3.2; 98% vs 32%), KRT10 (3.1; 98% vs 49%), SFN (3.1; 98% vs 45%), LGALS7B (2.9; 97% vs 14%), PERP (2.7; 98% vs 42%), KRTDAP (2.7; 89% vs 12%), LY6D (2.6; 96% vs 23%), S100A14 (2.5; 98% vs 29%), LYPD3 (2.1; 91% vs 18%), AQP3 (2.1; 94% vs 24%), DSP (2.1; 94% vs 19%), TACSTD2 (1.7; 91% vs 24%), SERPINB5 (1.7; 90% vs 16%), KRT14 (1.6; 95% vs 67%), CCL27 (1.5; 86% vs 12%), RNF144B (1.5; 79% vs 19%), MIR205HG (1.4; 88% vs 21%), CLDN1 (1.4; 81% vs 11%), FXYD3 (1.4; 86% vs 17%)
- **Claim:** CL:0000312 *keratinocyte*
- Cited markers: KRT1 (supports), DMKN (supports), KRT10 (supports), SFN (supports), LGALS7B (supports), PERP (supports), KRTDAP (supports), LY6D (supports), S100A14 (supports), LYPD3 (supports), AQP3 (supports), DSP (supports), TACSTD2 (supports), SERPINB5 (supports), CCL27 (supports), CLDN1 (supports)

## 35. `sc-2d06b761bbe6`

- Cluster `c03` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): C1QA (3.6; 100% vs 14%), C1QB (3.5; 99% vs 11%), CD163 (2.9; 99% vs 10%), HLA-DRA (2.7; 98% vs 22%), CTSB (2.6; 99% vs 38%), MARCO (2.6; 86% vs 4%), FTL (2.5; 100% vs 100%), SLC40A1 (2.5; 94% vs 32%), C1QC (2.5; 95% vs 8%), MS4A6A (2.4; 95% vs 17%), CD74 (2.3; 98% vs 40%), MS4A7 (2.3; 91% vs 8%), CTSS (2.3; 96% vs 24%), AIF1 (2.2; 95% vs 15%), TYROBP (2.2; 97% vs 28%), NPC2 (2.2; 97% vs 42%), SAT1 (2.2; 100% vs 72%), GPX1 (2.1; 99% vs 66%), HMOX1 (2.1; 85% vs 9%), FCER1G (2.1; 94% vs 24%)
- **Claim:** CL:0000091 *Kupffer cell*
- Cited markers: C1QA (supports), C1QB (supports), C1QC (supports), CD163 (supports), MARCO (supports), SLC40A1 (supports), HMOX1 (supports), MS4A7 (supports), MS4A6A (supports), HLA-DRA (supports), CD74 (supports), AIF1 (supports), CTSS (supports), TYROBP (supports), FCER1G (supports), FTL (supports)

## 36. `sc-74db4609c7a9`

- Cluster `c07` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (1.3; 97% vs 57%), CXCR4 (1.3; 89% vs 50%), IL32 (1.3; 93% vs 62%), GZMK (1.2; 77% vs 28%), IL7R (1.1; 85% vs 36%), TRDV2 (1.1; 44% vs 4%), S100A4 (1.1; 91% vs 62%), TNFAIP3 (1.0; 86% vs 60%), DUSP2 (0.9; 93% vs 80%), SPOCK2 (0.9; 86% vs 44%), KLRB1 (0.9; 94% vs 73%), NFKBIA (0.9; 94% vs 81%), TC2N (0.9; 74% vs 28%), S100A6 (0.9; 81% vs 45%), CD3E (0.9; 92% vs 67%), IL23R (0.8; 57% vs 9%), CD69 (0.8; 98% vs 92%), FOSB (0.7; 90% vs 74%), DUSP1 (0.7; 99% vs 93%), SLC4A10 (0.7; 50% vs 5%)
- **Claim:** CL:0000798 *gamma-delta T cell*
- Cited markers: TRDV2 (supports), CD3E (supports), IL7R (supports), KLRB1 (supports), IL23R (supports), SLC4A10 (supports), GZMK (supports), IL32 (supports), TC2N (supports)

## 37. `sc-554e5e45515f`

- Cluster `c15` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): UMOD (3.4; 85% vs 18%), SLC12A1 (3.0; 96% vs 5%), DEFB1 (2.4; 99% vs 34%), KNG1 (1.9; 83% vs 12%), ATP1B1 (1.8; 99% vs 56%), MT-ND1 (1.7; 100% vs 94%), ATP1A1 (1.7; 98% vs 52%), MALAT1 (1.7; 100% vs 83%), CD24 (1.6; 98% vs 41%), S100A6 (1.5; 100% vs 64%), MT-ND2 (1.5; 100% vs 96%), MT-CYB (1.5; 100% vs 96%), MT-CO1 (1.5; 100% vs 99%), MT-CO3 (1.5; 100% vs 99%), MT-ND4 (1.5; 100% vs 97%), MT-ATP6 (1.4; 100% vs 97%), MT-ND3 (1.4; 100% vs 97%), MT-CO2 (1.3; 100% vs 98%), CA12 (1.3; 92% vs 26%), S100A2 (1.2; 70% vs 18%)
- **Claim:** CL:0002306 *thick ascending limb cell*
- Cited markers: UMOD (supports), SLC12A1 (supports), ATP1A1 (supports), ATP1B1 (supports), CA12 (supports)

## 38. `sc-c7c4c2041f88`

- Cluster `c01` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CD52 (2.2; 87% vs 16%), IL32 (2.1; 86% vs 28%), SRGN (1.9; 94% vs 43%), CD3D (1.6; 71% vs 5%), ARHGDIB (1.6; 80% vs 23%), CXCR4 (1.5; 68% vs 16%), CD69 (1.4; 63% vs 6%), CREM (1.4; 76% vs 41%), PTPRCAP (1.4; 65% vs 4%), SARAF (1.3; 77% vs 36%), DUSP2 (1.3; 67% vs 21%), HCST (1.3; 67% vs 15%), PTPRC (1.2; 63% vs 9%), LTB (1.2; 54% vs 6%), SAMSN1 (1.2; 60% vs 10%), FXYD5 (1.1; 76% vs 39%), ALOX5AP (1.1; 59% vs 12%), STK17B (1.1; 63% vs 17%), S100A4 (1.1; 97% vs 86%), RGCC (1.1; 67% vs 34%)
- **Claim:** CL:0000084 *T cell*
- Cited markers: CD3D (supports), IL32 (supports), CD52 (supports), LTB (supports), PTPRC (supports), PTPRCAP (supports), CD69 (supports), CXCR4 (supports), HCST (supports), ARHGDIB (supports), SRGN (supports), DUSP2 (supports), STK17B (supports), SAMSN1 (supports)

## 39. `sc-b93c03bf06d2`

- Cluster `c06` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): HLA-DPB1 (4.1; 100% vs 22%), HLA-DPA1 (4.0; 100% vs 30%), C1QA (3.6; 89% vs 13%), C1QC (3.5; 87% vs 8%), C1QB (3.5; 87% vs 10%), TYROBP (3.4; 95% vs 9%), HLA-DRA (3.2; 100% vs 70%), TMSB4X (3.1; 100% vs 100%), HLA-DQA1 (3.0; 99% vs 4%), CD74 (3.0; 100% vs 95%), HLA-DRB1 (3.0; 100% vs 64%), CST3 (2.7; 100% vs 84%), AIF1 (2.7; 100% vs 5%), LYZ (2.6; 97% vs 23%), MS4A6A (2.6; 96% vs 3%), HLA-DQB1 (2.5; 99% vs 24%), SELENOP (2.3; 81% vs 64%), NPC2 (2.0; 100% vs 76%), FCER1G (2.0; 93% vs 5%), HLA-DMA (2.0; 96% vs 37%)
- **Claim:** CL:0000235 *macrophage*
- Cited markers: HLA-DPB1 (supports), HLA-DPA1 (supports), C1QA (supports), C1QC (supports), C1QB (supports), TYROBP (supports), HLA-DRA (supports), TMSB4X (supports), HLA-DQA1 (supports), CD74 (supports), HLA-DRB1 (supports), CST3 (supports), AIF1 (supports), LYZ (supports), MS4A6A (supports), HLA-DQB1 (supports), SELENOP (supports), NPC2 (supports), FCER1G (supports), HLA-DMA (supports)

## 40. `sc-0ed3dae30cb0`

- Cluster `c10` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): KRT14 (3.7; 100% vs 67%), S100A2 (3.2; 99% vs 46%), KRT5 (3.0; 99% vs 34%), SFN (2.9; 100% vs 46%), DST (2.3; 97% vs 30%), MIR205HG (2.2; 96% vs 21%), SERPINB2 (2.2; 89% vs 18%), PERP (2.1; 98% vs 43%), AQP3 (1.9; 92% vs 25%), S100A14 (1.8; 92% vs 30%), TACSTD2 (1.8; 92% vs 25%), LGALS7B (1.8; 90% vs 16%), ERRFI1 (1.6; 87% vs 27%), SERPINB5 (1.6; 88% vs 18%), AREG (1.5; 68% vs 8%), RND3 (1.5; 88% vs 37%), FGFBP1 (1.5; 79% vs 17%), CCL27 (1.4; 82% vs 13%), KRT15 (1.4; 70% vs 11%), ACTG1 (1.3; 100% vs 86%)
- **Claim:** CL:0000312 *keratinocyte*
- Cited markers: KRT14 (supports), S100A2 (supports), KRT5 (supports), SFN (supports), DST (supports), MIR205HG (supports), SERPINB2 (supports), PERP (supports), AQP3 (supports), S100A14 (supports), TACSTD2 (supports), LGALS7B (supports), ERRFI1 (supports), SERPINB5 (supports), AREG (supports), RND3 (supports), FGFBP1 (supports), CCL27 (supports), KRT15 (supports)

## 41. `sc-835f4e01b78e`

- Cluster `c03` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): SST (5.7; 100% vs 100%), RBP4 (2.6; 100% vs 68%), PCSK1 (1.2; 100% vs 53%), PRG4 (1.2; 80% vs 14%), BCHE (0.7; 76% vs 4%), LEPR (0.7; 93% vs 18%), SEC11C (0.6; 100% vs 96%), RGS2 (0.6; 81% vs 49%), AQP3 (0.5; 86% vs 44%), ISL1 (0.5; 100% vs 70%), TPPP3 (0.5; 89% vs 56%), CASR (0.4; 97% vs 37%), HHEX (0.4; 89% vs 12%), UCHL1 (0.4; 100% vs 71%), GABRG2 (0.4; 58% vs 8%), HADH (0.3; 97% vs 64%), UNC5B (0.3; 91% vs 31%), PCP4 (0.3; 92% vs 48%), DIRAS3 (0.3; 83% vs 36%), TENM3 (0.3; 96% vs 41%)
- **Claim:** CL:0000173 *pancreatic D cell*
- Cited markers: SST (supports), RBP4 (supports), PCSK1 (supports), ISL1 (supports), HHEX (supports), UCHL1 (supports)

## 42. `sc-dd56d93c4db8`

- Cluster `c07` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): GNLY (2.0; 57% vs 7%), NKG7 (1.8; 65% vs 23%), TMSB10 (1.3; 97% vs 76%), IGKC (1.2; 60% vs 34%), GZMB (1.2; 53% vs 4%), TUBA1B (1.2; 63% vs 31%), TMSB4X (1.2; 98% vs 89%), PTMA (1.1; 99% vs 91%), MALAT1 (1.1; 99% vs 97%), CORO1A (1.1; 75% vs 29%), CCL5 (1.1; 54% vs 20%), FGFBP2 (1.0; 45% vs 2%), KLRD1 (1.0; 55% vs 14%), PFN1 (1.0; 95% vs 79%), H4C3 (1.0; 64% vs 48%), HMGB2 (1.0; 57% vs 23%), HMGN2 (1.0; 69% vs 40%), CYBA (1.0; 84% vs 44%), CCL4 (1.0; 57% vs 22%), HLA-B (1.0; 96% vs 86%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: GNLY (supports), NKG7 (supports), GZMB (supports), FGFBP2 (supports), KLRD1 (supports), CCL5 (supports), CCL4 (supports), IGKC (contradicts)

## 43. `sc-1ecb98228b96`

- Cluster `c13` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): DEFB1 (3.3; 100% vs 38%), SLC12A3 (3.2; 98% vs 4%), TMEM52B (2.7; 100% vs 13%), KNG1 (2.4; 99% vs 16%), MT-ND1 (2.3; 100% vs 94%), WNK1 (2.1; 98% vs 28%), ATP1B1 (2.0; 100% vs 59%), SPP1 (2.0; 98% vs 57%), MT-CO1 (2.0; 100% vs 99%), MT-ND2 (1.9; 100% vs 97%), MT-CO3 (1.9; 100% vs 99%), MT-ATP6 (1.8; 100% vs 97%), MT-ND4 (1.8; 100% vs 97%), MT-CYB (1.8; 100% vs 96%), CA12 (1.7; 98% vs 30%), MALAT1 (1.7; 100% vs 84%), MT-CO2 (1.7; 100% vs 98%), MT-ND5 (1.7; 100% vs 87%), ATP1A1 (1.6; 99% vs 55%), MT-ND3 (1.6; 100% vs 97%)
- **Claim:** CL:1000849 *kidney distal convoluted tubule epithelial cell*
- Cited markers: SLC12A3 (supports), TMEM52B (supports), KNG1 (supports), WNK1 (supports), DEFB1 (supports), CA12 (supports), ATP1B1 (supports), ATP1A1 (supports), SPP1 (supports)

## 44. `sc-734a08d5281e`

- Cluster `c05` of a Homo sapiens zone of skin dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): KRT1 (3.3; 97% vs 30%), DMKN (3.2; 98% vs 32%), KRT10 (3.1; 98% vs 49%), SFN (3.1; 98% vs 45%), LGALS7B (2.9; 97% vs 14%), PERP (2.7; 98% vs 42%), KRTDAP (2.7; 89% vs 12%), LY6D (2.6; 96% vs 23%), S100A14 (2.5; 98% vs 29%), LYPD3 (2.1; 91% vs 18%), AQP3 (2.1; 94% vs 24%), DSP (2.1; 94% vs 19%), TACSTD2 (1.7; 91% vs 24%), SERPINB5 (1.7; 90% vs 16%), KRT14 (1.6; 95% vs 67%), CCL27 (1.5; 86% vs 12%), RNF144B (1.5; 79% vs 19%), MIR205HG (1.4; 88% vs 21%), CLDN1 (1.4; 81% vs 11%), FXYD3 (1.4; 86% vs 17%)
- **Claim:** CL:0000312 *keratinocyte*
- Cited markers: KRT1 (supports), DMKN (supports), KRT10 (supports), SFN (supports), LGALS7B (supports), PERP (supports), KRTDAP (supports), LY6D (supports), S100A14 (supports), LYPD3 (supports), AQP3 (supports), DSP (supports), TACSTD2 (supports), SERPINB5 (supports), KRT14 (supports), CCL27 (supports), RNF144B (supports), MIR205HG (supports), CLDN1 (supports), FXYD3 (supports)

## 45. `sc-c5207ef0df45`

- Cluster `c07` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (1.3; 97% vs 57%), CXCR4 (1.3; 89% vs 50%), IL32 (1.3; 93% vs 62%), GZMK (1.2; 77% vs 28%), IL7R (1.1; 85% vs 36%), TRDV2 (1.1; 44% vs 4%), S100A4 (1.1; 91% vs 62%), TNFAIP3 (1.0; 86% vs 60%), DUSP2 (0.9; 93% vs 80%), SPOCK2 (0.9; 86% vs 44%), KLRB1 (0.9; 94% vs 73%), NFKBIA (0.9; 94% vs 81%), TC2N (0.9; 74% vs 28%), S100A6 (0.9; 81% vs 45%), CD3E (0.9; 92% vs 67%), IL23R (0.8; 57% vs 9%), CD69 (0.8; 98% vs 92%), FOSB (0.7; 90% vs 74%), DUSP1 (0.7; 99% vs 93%), SLC4A10 (0.7; 50% vs 5%)
- **Claim:** CL:0000940 *mucosal invariant T cell*
- Cited markers: LTB (supports), CXCR4 (supports), IL32 (supports), GZMK (supports), IL7R (supports), TRDV2 (contradicts), S100A4 (supports), TNFAIP3 (supports), DUSP2 (supports), SPOCK2 (supports), KLRB1 (supports), NFKBIA (supports), TC2N (supports), S100A6 (supports), CD3E (supports), IL23R (supports), CD69 (supports), FOSB (supports), DUSP1 (supports), SLC4A10 (supports)

## 46. `sc-c92402aae05f`

- Cluster `c07` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): COL1A1 (5.5; 100% vs 57%), SPARC (4.5; 100% vs 27%), COL3A1 (4.4; 100% vs 25%), COL1A2 (4.3; 100% vs 32%), FN1 (3.7; 100% vs 19%), COL6A1 (3.5; 100% vs 37%), COL6A3 (3.5; 100% vs 10%), COL4A2 (3.3; 100% vs 24%), COL5A1 (3.2; 100% vs 12%), COL15A1 (3.1; 96% vs 9%), COL5A2 (3.0; 100% vs 11%), TIMP1 (3.0; 100% vs 84%), MICAL2 (2.9; 100% vs 29%), PXDN (2.8; 100% vs 14%), CALD1 (2.8; 100% vs 43%), SERPINE1 (2.7; 97% vs 13%), IGFBP7 (2.6; 99% vs 87%), VIM (2.6; 100% vs 48%), CYGB (2.6; 97% vs 8%), SFRP2 (2.6; 96% vs 6%)
- **Claim:** CL:0000057 *fibroblast*
- Cited markers: COL1A1 (supports), COL3A1 (supports), COL1A2 (supports), COL6A1 (supports), COL6A3 (supports), COL4A2 (supports), COL5A1 (supports), COL5A2 (supports), COL15A1 (supports), SPARC (supports), FN1 (supports), SFRP2 (supports), CYGB (supports)

## 47. `sc-42f3008ea7cd`

- Cluster `c10` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): TFF3 (5.2; 100% vs 38%), SPINK4 (4.1; 93% vs 20%), CLCA1 (3.6; 98% vs 7%), ZG16 (2.9; 95% vs 52%), MUC2 (2.7; 94% vs 7%), REG4 (2.6; 89% vs 11%), ITLN1 (2.1; 89% vs 4%), AGR2 (2.0; 94% vs 55%), RNASE1 (1.8; 94% vs 14%), SH3BGRL3 (1.7; 100% vs 82%), SPINK1 (1.5; 100% vs 69%), GSN (1.5; 89% vs 34%), LGALS4 (1.5; 100% vs 82%), STARD10 (1.4; 96% vs 33%), KRT18 (1.3; 100% vs 74%), FXYD3 (1.3; 94% vs 49%), CDC42EP5 (1.2; 95% vs 45%), KLK1 (1.2; 84% vs 14%), ST6GALNAC1 (1.2; 84% vs 28%), LRRC26 (1.2; 75% vs 10%)
- **Claim:** CL:0000160 *goblet cell*
- Cited markers: MUC2 (supports), TFF3 (supports), CLCA1 (supports), ITLN1 (supports), AGR2 (supports), SPINK4 (supports), REG4 (supports), ZG16 (supports)

## 48. `sc-8202e57eff36`

- Cluster `c03` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): HLA-DRA (3.4; 100% vs 41%), CD74 (3.2; 100% vs 61%), HLA-DPA1 (3.2; 98% vs 25%), HLA-DPB1 (3.1; 98% vs 24%), SRGN (3.0; 98% vs 31%), HLA-DRB1 (2.9; 99% vs 38%), TYROBP (2.7; 98% vs 6%), CXCL8 (2.4; 72% vs 20%), HLA-DQB1 (2.4; 93% vs 18%), IL1B (2.3; 72% vs 8%), GPR183 (2.2; 86% vs 5%), TMSB4X (2.2; 100% vs 74%), HLA-DQA1 (2.2; 93% vs 14%), PLAUR (2.1; 88% vs 15%), RGS1 (2.1; 82% vs 6%), NFKBIA (2.1; 94% vs 56%), RGS2 (2.0; 88% vs 22%), AIF1 (2.0; 92% vs 4%), CCL3 (1.9; 58% vs 12%), CXCL2 (1.8; 72% vs 26%)
- **Claim:** CL:0000451 *dendritic cell*
- Cited markers: HLA-DRA (supports), CD74 (supports), HLA-DPA1 (supports), HLA-DPB1 (supports), HLA-DRB1 (supports), HLA-DQB1 (supports), HLA-DQA1 (supports), GPR183 (supports), TYROBP (supports), AIF1 (supports), SRGN (supports), CXCL8 (supports), IL1B (supports), CCL3 (supports)

## 49. `sc-919d16f1e63f`

- Cluster `c08` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): IL32 (1.2; 93% vs 62%), GZMK (1.1; 71% vs 28%), CD3E (1.0; 98% vs 67%), ITM2C (0.9; 74% vs 35%), CD27 (0.9; 85% vs 37%), TRDV2 (0.8; 35% vs 4%), AIF1 (0.7; 82% vs 38%), CNN2 (0.7; 92% vs 64%), CXCR3 (0.7; 71% vs 20%), ZNF683 (0.7; 37% vs 4%), CD8A (0.7; 61% vs 33%), CD52 (0.7; 95% vs 68%), COTL1 (0.7; 80% vs 59%), SIRPG (0.6; 65% vs 23%), CD3D (0.6; 97% vs 69%), ID3 (0.6; 64% vs 32%), TCF7 (0.6; 73% vs 37%), CXCR4 (0.5; 80% vs 50%), LTB (0.5; 87% vs 57%), XCL1 (0.5; 74% vs 47%)
- **Claim:** CL:0000625 *CD8-positive, alpha-beta T cell*
- Cited markers: CD3E (supports), CD3D (supports), CD8A (supports), GZMK (supports), CD27 (supports), CXCR3 (supports), TCF7 (supports), ZNF683 (supports), IL32 (supports), CD52 (supports)

## 50. `sc-3e8815615c78`

- Cluster `c07` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): COL1A1 (5.5; 100% vs 57%), SPARC (4.5; 100% vs 27%), COL3A1 (4.4; 100% vs 25%), COL1A2 (4.3; 100% vs 32%), FN1 (3.7; 100% vs 19%), COL6A1 (3.5; 100% vs 37%), COL6A3 (3.5; 100% vs 10%), COL4A2 (3.3; 100% vs 24%), COL5A1 (3.2; 100% vs 12%), COL15A1 (3.1; 96% vs 9%), COL5A2 (3.0; 100% vs 11%), TIMP1 (3.0; 100% vs 84%), MICAL2 (2.9; 100% vs 29%), PXDN (2.8; 100% vs 14%), CALD1 (2.8; 100% vs 43%), SERPINE1 (2.7; 97% vs 13%), IGFBP7 (2.6; 99% vs 87%), VIM (2.6; 100% vs 48%), CYGB (2.6; 97% vs 8%), SFRP2 (2.6; 96% vs 6%)
- **Claim:** CL:0002410 *pancreatic stellate cell*
- Cited markers: COL1A1 (supports), COL1A2 (supports), COL3A1 (supports), SPARC (supports), FN1 (supports), COL6A1 (supports), COL6A3 (supports), CYGB (supports), SFRP2 (supports)

## 51. `sc-28afeb3a02f1`

- Cluster `c03` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): HLA-DRA (3.4; 100% vs 41%), CD74 (3.2; 100% vs 61%), HLA-DPA1 (3.2; 98% vs 25%), HLA-DPB1 (3.1; 98% vs 24%), SRGN (3.0; 98% vs 31%), HLA-DRB1 (2.9; 99% vs 38%), TYROBP (2.7; 98% vs 6%), CXCL8 (2.4; 72% vs 20%), HLA-DQB1 (2.4; 93% vs 18%), IL1B (2.3; 72% vs 8%), GPR183 (2.2; 86% vs 5%), TMSB4X (2.2; 100% vs 74%), HLA-DQA1 (2.2; 93% vs 14%), PLAUR (2.1; 88% vs 15%), RGS1 (2.1; 82% vs 6%), NFKBIA (2.1; 94% vs 56%), RGS2 (2.0; 88% vs 22%), AIF1 (2.0; 92% vs 4%), CCL3 (1.9; 58% vs 12%), CXCL2 (1.8; 72% vs 26%)
- **Claim:** CL:0000235 *macrophage*
- Cited markers: HLA-DRA (supports), CD74 (supports), HLA-DPA1 (supports), HLA-DPB1 (supports), HLA-DRB1 (supports), TYROBP (supports), AIF1 (supports), IL1B (supports), CCL3 (supports)

## 52. `sc-856e7a60cdcd`

- Cluster `c10` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): DNASE1L3 (2.8; 96% vs 13%), PRSS23 (2.7; 92% vs 10%), TIMP1 (2.5; 98% vs 33%), RAMP3 (2.4; 94% vs 8%), IGFBP7 (2.3; 96% vs 16%), ID1 (2.3; 91% vs 20%), LIFR (2.3; 91% vs 10%), INMT (2.2; 88% vs 5%), TIMP3 (2.2; 92% vs 17%), ID3 (2.1; 87% vs 12%), RNASE1 (2.1; 90% vs 11%), TAGLN (2.1; 73% vs 4%), ENG (2.1; 90% vs 10%), IFI27 (1.9; 86% vs 10%), HSPG2 (1.9; 87% vs 8%), C7 (1.9; 79% vs 7%), HLA-E (1.8; 97% vs 59%), PTPRB (1.8; 86% vs 8%), FCN3 (1.7; 66% vs 14%), PLAC8 (1.7; 87% vs 24%)
- **Claim:** CL:0000632 *hepatic stellate cell*
- Cited markers: TIMP1 (supports), TIMP3 (supports), IGFBP7 (supports), TAGLN (supports), HSPG2 (supports), RAMP3 (supports), LIFR (supports), ID1 (supports), ID3 (supports), PRSS23 (supports), ENG (supports)

## 53. `sc-6a41569ec051`

- Cluster `c12` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (2.2; 99% vs 57%), IL7R (2.1; 98% vs 35%), IL4I1 (1.6; 84% vs 5%), LST1 (1.5; 86% vs 17%), CCR6 (1.4; 86% vs 4%), VIM (1.4; 96% vs 66%), S100A4 (1.4; 92% vs 62%), RORC (1.4; 82% vs 6%), S100A6 (1.4; 89% vs 44%), TNFAIP3 (1.3; 96% vs 60%), AQP3 (1.3; 88% vs 30%), RGS1 (1.2; 92% vs 54%), ITM2C (1.1; 85% vs 34%), JAML (1.0; 76% vs 17%), DDIT4 (1.0; 90% vs 60%), CXCR4 (1.0; 86% vs 50%), KIT (1.0; 66% vs 4%), TMIGD2 (0.9; 84% vs 46%), IL23R (0.9; 70% vs 8%), ZFP36L1 (0.9; 98% vs 88%)
- **Claim:** CL:0001071 *group 3 innate lymphoid cell*
- Cited markers: RORC (supports), IL7R (supports), KIT (supports), IL23R (supports), CCR6 (supports), LTB (supports)

## 54. `sc-c3eb60920f61`

- Cluster `c03` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): C1QA (3.6; 100% vs 14%), C1QB (3.5; 99% vs 11%), CD163 (2.9; 99% vs 10%), HLA-DRA (2.7; 98% vs 22%), CTSB (2.6; 99% vs 38%), MARCO (2.6; 86% vs 4%), FTL (2.5; 100% vs 100%), SLC40A1 (2.5; 94% vs 32%), C1QC (2.5; 95% vs 8%), MS4A6A (2.4; 95% vs 17%), CD74 (2.3; 98% vs 40%), MS4A7 (2.3; 91% vs 8%), CTSS (2.3; 96% vs 24%), AIF1 (2.2; 95% vs 15%), TYROBP (2.2; 97% vs 28%), NPC2 (2.2; 97% vs 42%), SAT1 (2.2; 100% vs 72%), GPX1 (2.1; 99% vs 66%), HMOX1 (2.1; 85% vs 9%), FCER1G (2.1; 94% vs 24%)
- **Claim:** CL:0000091 *Kupffer cell*
- Cited markers: MARCO (supports), CD163 (supports), C1QA (supports), C1QB (supports), C1QC (supports), SLC40A1 (supports), HMOX1 (supports), MS4A7 (supports)

## 55. `sc-080a4ad54b3b`

- Cluster `c11` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): FXYD4 (2.8; 83% vs 8%), AQP2 (2.7; 80% vs 4%), AQP3 (2.1; 80% vs 12%), MALAT1 (2.1; 100% vs 84%), MT-CO1 (1.6; 100% vs 99%), CLU (1.6; 84% vs 39%), WFDC2 (1.6; 78% vs 20%), TACSTD2 (1.6; 78% vs 21%), GDF15 (1.5; 80% vs 29%), MT-CO2 (1.4; 100% vs 98%), S100A6 (1.4; 92% vs 67%), MT-CO3 (1.4; 100% vs 99%), CDH16 (1.3; 86% vs 32%), KRT19 (1.3; 68% vs 10%), MT-ND4 (1.3; 100% vs 98%), KRT18 (1.3; 83% vs 38%), MT-CYB (1.3; 100% vs 97%), ELF3 (1.2; 76% vs 25%), MT-ATP6 (1.2; 100% vs 97%), NEAT1 (1.2; 97% vs 69%)
- **Claim:** CL:1001431 *kidney collecting duct principal cell*
- Cited markers: FXYD4 (supports), AQP2 (supports), AQP3 (supports), CDH16 (supports)

## 56. `sc-b27ceddaabda`

- Cluster `c09` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): CCL3 (2.0; 87% vs 34%), CCL4 (1.8; 96% vs 47%), NKG7 (1.7; 100% vs 66%), TYROBP (1.7; 98% vs 49%), XCL1 (1.5; 90% vs 40%), IL2RB (1.5; 94% vs 50%), GZMK (1.5; 82% vs 19%), CCL5 (1.5; 80% vs 48%), GZMA (1.2; 97% vs 65%), TRDC (1.2; 84% vs 39%), KLRB1 (1.2; 99% vs 69%), XCL2 (1.2; 85% vs 41%), ALOX5AP (1.2; 91% vs 58%), CMC1 (1.2; 87% vs 57%), ITM2C (1.1; 66% vs 30%), KLRC1 (1.1; 83% vs 39%), GSTP1 (1.0; 88% vs 57%), CST7 (1.0; 96% vs 53%), IER2 (1.0; 99% vs 94%), SRGN (1.0; 99% vs 90%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: NKG7 (supports), TYROBP (supports), IL2RB (supports), KLRC1 (supports), XCL1 (supports), XCL2 (supports), CST7 (supports), GZMA (supports), GZMK (supports), CCL5 (supports)

## 57. `sc-3e4827f1cf8e`

- Cluster `c03` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): SST (5.7; 100% vs 100%), RBP4 (2.6; 100% vs 68%), PCSK1 (1.2; 100% vs 53%), PRG4 (1.2; 80% vs 14%), BCHE (0.7; 76% vs 4%), LEPR (0.7; 93% vs 18%), SEC11C (0.6; 100% vs 96%), RGS2 (0.6; 81% vs 49%), AQP3 (0.5; 86% vs 44%), ISL1 (0.5; 100% vs 70%), TPPP3 (0.5; 89% vs 56%), CASR (0.4; 97% vs 37%), HHEX (0.4; 89% vs 12%), UCHL1 (0.4; 100% vs 71%), GABRG2 (0.4; 58% vs 8%), HADH (0.3; 97% vs 64%), UNC5B (0.3; 91% vs 31%), PCP4 (0.3; 92% vs 48%), DIRAS3 (0.3; 83% vs 36%), TENM3 (0.3; 96% vs 41%)
- **Claim:** CL:0000173 *pancreatic D cell*
- Cited markers: SST (supports), HHEX (supports), RBP4 (supports), LEPR (supports), PCSK1 (supports), ISL1 (supports)

## 58. `sc-fbc3fa6e37a7`

- Cluster `c07` of a Homo sapiens caudate lobe of liver dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): GNLY (2.0; 57% vs 7%), NKG7 (1.8; 65% vs 23%), TMSB10 (1.3; 97% vs 76%), IGKC (1.2; 60% vs 34%), GZMB (1.2; 53% vs 4%), TUBA1B (1.2; 63% vs 31%), TMSB4X (1.2; 98% vs 89%), PTMA (1.1; 99% vs 91%), MALAT1 (1.1; 99% vs 97%), CORO1A (1.1; 75% vs 29%), CCL5 (1.1; 54% vs 20%), FGFBP2 (1.0; 45% vs 2%), KLRD1 (1.0; 55% vs 14%), PFN1 (1.0; 95% vs 79%), H4C3 (1.0; 64% vs 48%), HMGB2 (1.0; 57% vs 23%), HMGN2 (1.0; 69% vs 40%), CYBA (1.0; 84% vs 44%), CCL4 (1.0; 57% vs 22%), HLA-B (1.0; 96% vs 86%)
- **Claim:** CL:0000623 *natural killer cell*
- Cited markers: NKG7 (supports), GNLY (supports), GZMB (supports), KLRD1 (supports), CCL5 (supports), CCL4 (supports), CORO1A (supports), IGKC (contradicts)

## 59. `sc-eab9c0d47ac4`

- Cluster `c05` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): LYZ (2.9; 98% vs 25%), MT1G (2.4; 98% vs 77%), GUCA2B (2.2; 61% vs 25%), BEST4 (2.2; 74% vs 1%), SPIB (2.0; 84% vs 4%), MT2A (1.9; 96% vs 82%), MT1E (1.8; 99% vs 70%), MT1H (1.8; 82% vs 52%), CFTR (1.7; 92% vs 28%), MT1X (1.6; 96% vs 60%), GSN (1.5; 82% vs 34%), CPA2 (1.4; 75% vs 3%), CA7 (1.4; 68% vs 1%), KRT20 (1.4; 83% vs 44%), CTSE (1.2; 90% vs 29%), GUCA2A (1.2; 50% vs 2%), FXYD3 (1.2; 94% vs 49%), S100A6 (1.2; 100% vs 95%), MT1M (1.1; 74% vs 27%), STARD10 (1.1; 94% vs 32%)
- **Claim:** CL:0002071 *enterocyte of epithelium of small intestine*
- Cited markers: BEST4 (supports), CA7 (supports), SPIB (supports), CFTR (supports), GUCA2B (supports), GUCA2A (supports), CPA2 (supports), CTSE (supports), KRT20 (supports)

## 60. `sc-c11395392128`

- Cluster `c12` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (2.2; 99% vs 57%), IL7R (2.1; 98% vs 35%), IL4I1 (1.6; 84% vs 5%), LST1 (1.5; 86% vs 17%), CCR6 (1.4; 86% vs 4%), VIM (1.4; 96% vs 66%), S100A4 (1.4; 92% vs 62%), RORC (1.4; 82% vs 6%), S100A6 (1.4; 89% vs 44%), TNFAIP3 (1.3; 96% vs 60%), AQP3 (1.3; 88% vs 30%), RGS1 (1.2; 92% vs 54%), ITM2C (1.1; 85% vs 34%), JAML (1.0; 76% vs 17%), DDIT4 (1.0; 90% vs 60%), CXCR4 (1.0; 86% vs 50%), KIT (1.0; 66% vs 4%), TMIGD2 (0.9; 84% vs 46%), IL23R (0.9; 70% vs 8%), ZFP36L1 (0.9; 98% vs 88%)
- **Claim:** CL:0001071 *group 3 innate lymphoid cell*
- Cited markers: IL7R (supports), CCR6 (supports), RORC (supports), IL23R (supports), KIT (supports), LTB (supports), JAML (supports), LST1 (contradicts)

## 61. `sc-1bd2021fc890`

- Cluster `c05` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): LYZ (2.9; 98% vs 25%), MT1G (2.4; 98% vs 77%), GUCA2B (2.2; 61% vs 25%), BEST4 (2.2; 74% vs 1%), SPIB (2.0; 84% vs 4%), MT2A (1.9; 96% vs 82%), MT1E (1.8; 99% vs 70%), MT1H (1.8; 82% vs 52%), CFTR (1.7; 92% vs 28%), MT1X (1.6; 96% vs 60%), GSN (1.5; 82% vs 34%), CPA2 (1.4; 75% vs 3%), CA7 (1.4; 68% vs 1%), KRT20 (1.4; 83% vs 44%), CTSE (1.2; 90% vs 29%), GUCA2A (1.2; 50% vs 2%), FXYD3 (1.2; 94% vs 49%), S100A6 (1.2; 100% vs 95%), MT1M (1.1; 74% vs 27%), STARD10 (1.1; 94% vs 32%)
- **Claim:** CL:0000584 *enterocyte*
- Cited markers: BEST4 (supports), CA7 (supports), CFTR (supports), GUCA2A (supports), GUCA2B (supports), KRT20 (supports)

## 62. `sc-37758b97b56f`

- Cluster `c12` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (2.2; 99% vs 57%), IL7R (2.1; 98% vs 35%), IL4I1 (1.6; 84% vs 5%), LST1 (1.5; 86% vs 17%), CCR6 (1.4; 86% vs 4%), VIM (1.4; 96% vs 66%), S100A4 (1.4; 92% vs 62%), RORC (1.4; 82% vs 6%), S100A6 (1.4; 89% vs 44%), TNFAIP3 (1.3; 96% vs 60%), AQP3 (1.3; 88% vs 30%), RGS1 (1.2; 92% vs 54%), ITM2C (1.1; 85% vs 34%), JAML (1.0; 76% vs 17%), DDIT4 (1.0; 90% vs 60%), CXCR4 (1.0; 86% vs 50%), KIT (1.0; 66% vs 4%), TMIGD2 (0.9; 84% vs 46%), IL23R (0.9; 70% vs 8%), ZFP36L1 (0.9; 98% vs 88%)
- **Claim:** CL:0001071 *group 3 innate lymphoid cell*
- Cited markers: IL7R (supports), RORC (supports), KIT (supports), CCR6 (supports), IL23R (supports), LTB (supports)

## 63. `sc-0e9dd71166b2`

- Cluster `c06` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): PPY (6.4; 100% vs 54%), SCG2 (2.0; 100% vs 90%), PEG10 (2.0; 100% vs 88%), ID2 (1.8; 98% vs 73%), PAX6 (1.7; 100% vs 79%), ETV1 (1.6; 99% vs 41%), AQP3 (1.6; 90% vs 46%), MEIS2 (1.5; 98% vs 75%), ITM2C (1.3; 99% vs 92%), PCSK2 (1.2; 100% vs 94%), CHGB (1.2; 100% vs 93%), THSD7A (1.2; 86% vs 14%), PAM (1.2; 100% vs 94%), GAD2 (1.2; 98% vs 70%), NEUROD1 (1.2; 99% vs 80%), SERTM1 (1.1; 84% vs 9%), ABCC9 (1.1; 96% vs 71%), UCHL1 (1.1; 97% vs 72%), ABCC8 (1.1; 99% vs 73%), SLC6A4 (1.1; 91% vs 56%)
- **Claim:** CL:0002275 *pancreatic PP cell*
- Cited markers: PPY (supports), SCG2 (supports), PAX6 (supports), PCSK2 (supports), CHGB (supports), NEUROD1 (supports)

## 64. `sc-06c333c4660a`

- Cluster `c02` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): CXCR4 (2.2; 83% vs 14%), MALAT1 (2.1; 100% vs 84%), RPS29 (2.0; 100% vs 97%), RPS27 (1.9; 100% vs 99%), TMSB4X (1.9; 99% vs 74%), BTG1 (1.8; 94% vs 67%), SRGN (1.6; 80% vs 32%), CD52 (1.6; 65% vs 5%), RPL17 (1.5; 89% vs 70%), RPS3 (1.5; 100% vs 92%), RPS15A (1.5; 100% vs 96%), IL7R (1.5; 57% vs 2%), RPS19 (1.5; 99% vs 96%), CD2 (1.5; 59% vs 1%), RPLP2 (1.4; 100% vs 98%), RPS2 (1.4; 99% vs 91%), PTPRC (1.4; 61% vs 7%), RPL41 (1.4; 100% vs 99%), B2M (1.4; 100% vs 96%), RPS21 (1.4; 97% vs 89%)
- **Claim:** CL:0000084 *T cell*
- Cited markers: CD2 (supports), IL7R (supports), CD52 (supports), PTPRC (supports)

## 65. `sc-7f4823b086ad`

- Cluster `c03` of a Homo sapiens pancreas dataset (CEL-seq2)
- Top markers (log fold change; share of cells in vs out of the cluster): SST (5.7; 100% vs 100%), RBP4 (2.6; 100% vs 68%), PCSK1 (1.2; 100% vs 53%), PRG4 (1.2; 80% vs 14%), BCHE (0.7; 76% vs 4%), LEPR (0.7; 93% vs 18%), SEC11C (0.6; 100% vs 96%), RGS2 (0.6; 81% vs 49%), AQP3 (0.5; 86% vs 44%), ISL1 (0.5; 100% vs 70%), TPPP3 (0.5; 89% vs 56%), CASR (0.4; 97% vs 37%), HHEX (0.4; 89% vs 12%), UCHL1 (0.4; 100% vs 71%), GABRG2 (0.4; 58% vs 8%), HADH (0.3; 97% vs 64%), UNC5B (0.3; 91% vs 31%), PCP4 (0.3; 92% vs 48%), DIRAS3 (0.3; 83% vs 36%), TENM3 (0.3; 96% vs 41%)
- **Claim:** CL:0000173 *pancreatic D cell*
- Cited markers: SST (supports), HHEX (supports), RBP4 (supports), LEPR (supports), BCHE (supports), PRG4 (supports), CASR (supports), ISL1 (supports), PCSK1 (supports)

## 66. `sc-fd438ca2c872`

- Cluster `c05` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): LTB (1.6; 98% vs 52%), CD52 (1.4; 98% vs 64%), TCF7 (1.3; 91% vs 30%), LEF1 (1.3; 92% vs 29%), SELL (1.3; 88% vs 29%), IL7R (1.2; 84% vs 30%), LDHB (1.2; 97% vs 72%), CCR7 (1.1; 84% vs 20%), RGS10 (1.0; 90% vs 33%), NOSIP (1.0; 90% vs 51%), LRRN3 (0.9; 71% vs 10%), CD3E (0.9; 97% vs 63%), VIM (0.9; 95% vs 62%), RPS8 (0.9; 100% vs 100%), AIF1 (0.8; 82% vs 33%), CAMK4 (0.8; 79% vs 25%), RPL36A (0.8; 94% vs 78%), CD27 (0.8; 84% vs 32%), CORO1B (0.8; 76% vs 31%), CD40LG (0.8; 65% vs 7%)
- **Claim:** CL:0000895 *naive thymus-derived CD4-positive, alpha-beta T cell*
- Cited markers: CCR7 (supports), SELL (supports), LEF1 (supports), TCF7 (supports), LRRN3 (supports), IL7R (supports), CAMK4 (supports), CD27 (supports), LTB (supports), CD3E (supports), CD40LG (supports), NOSIP (supports)

## 67. `sc-01004e474ad5`

- Cluster `c09` of a Homo sapiens kidney dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): WFDC2 (2.9; 97% vs 21%), KRT7 (2.8; 100% vs 13%), IGFBP5 (2.0; 97% vs 35%), CA12 (1.9; 97% vs 33%), TMEM213 (1.9; 97% vs 21%), CD9 (1.8; 100% vs 50%), ATP6V1G3 (1.8; 90% vs 10%), MALAT1 (1.8; 100% vs 85%), ATP6V0B (1.7; 100% vs 52%), LGALS3 (1.7; 100% vs 39%), ATP6V0D2 (1.6; 94% vs 13%), TSPAN8 (1.6; 87% vs 8%), ATP6V1B1 (1.6; 94% vs 20%), KRT8 (1.4; 94% vs 38%), HEPACAM2 (1.4; 90% vs 8%), ATP6AP2 (1.4; 97% vs 44%), S100A2 (1.3; 81% vs 23%), ID3 (1.3; 87% vs 33%), IL18 (1.3; 90% vs 12%), SLC26A4 (1.3; 77% vs 1%)
- **Claim:** CL:0002201 *renal beta-intercalated cell*
- Cited markers: SLC26A4 (supports), ATP6V1B1 (supports), ATP6V0D2 (supports), ATP6V1G3 (supports), ATP6V0B (supports), ATP6AP2 (supports), TMEM213 (supports), HEPACAM2 (supports), CA12 (supports), WFDC2 (supports), KRT7 (supports), KRT8 (supports), TSPAN8 (supports)

## 68. `sc-8328256db783`

- Cluster `c08` of a Homo sapiens lung dataset (10x 5' v1)
- Top markers (log fold change; share of cells in vs out of the cluster): IL32 (1.2; 93% vs 62%), GZMK (1.1; 71% vs 28%), CD3E (1.0; 98% vs 67%), ITM2C (0.9; 74% vs 35%), CD27 (0.9; 85% vs 37%), TRDV2 (0.8; 35% vs 4%), AIF1 (0.7; 82% vs 38%), CNN2 (0.7; 92% vs 64%), CXCR3 (0.7; 71% vs 20%), ZNF683 (0.7; 37% vs 4%), CD8A (0.7; 61% vs 33%), CD52 (0.7; 95% vs 68%), COTL1 (0.7; 80% vs 59%), SIRPG (0.6; 65% vs 23%), CD3D (0.6; 97% vs 69%), ID3 (0.6; 64% vs 32%), TCF7 (0.6; 73% vs 37%), CXCR4 (0.5; 80% vs 50%), LTB (0.5; 87% vs 57%), XCL1 (0.5; 74% vs 47%)
- **Claim:** CL:0000625 *CD8-positive, alpha-beta T cell*
- Cited markers: CD3E (supports), CD3D (supports), CD8A (supports), GZMK (supports), CXCR3 (supports), TRDV2 (contradicts)

## 69. `sc-264c388c143f`

- Cluster `c06` of a Homo sapiens duodenum dataset (10x 3' v2)
- Top markers (log fold change; share of cells in vs out of the cluster): HLA-DPB1 (4.1; 100% vs 22%), HLA-DPA1 (4.0; 100% vs 30%), C1QA (3.6; 89% vs 13%), C1QC (3.5; 87% vs 8%), C1QB (3.5; 87% vs 10%), TYROBP (3.4; 95% vs 9%), HLA-DRA (3.2; 100% vs 70%), TMSB4X (3.1; 100% vs 100%), HLA-DQA1 (3.0; 99% vs 4%), CD74 (3.0; 100% vs 95%), HLA-DRB1 (3.0; 100% vs 64%), CST3 (2.7; 100% vs 84%), AIF1 (2.7; 100% vs 5%), LYZ (2.6; 97% vs 23%), MS4A6A (2.6; 96% vs 3%), HLA-DQB1 (2.5; 99% vs 24%), SELENOP (2.3; 81% vs 64%), NPC2 (2.0; 100% vs 76%), FCER1G (2.0; 93% vs 5%), HLA-DMA (2.0; 96% vs 37%)
- **Claim:** CL:0000235 *macrophage*
- Cited markers: C1QA (supports), C1QB (supports), C1QC (supports), AIF1 (supports), MS4A6A (supports), TYROBP (supports), FCER1G (supports), LYZ (supports), CD74 (supports), HLA-DRA (supports), HLA-DPB1 (supports), HLA-DPA1 (supports), HLA-DQA1 (supports), HLA-DRB1 (supports), HLA-DQB1 (supports), HLA-DMA (supports), CST3 (supports), SELENOP (supports), NPC2 (supports)
