## Known Limitations

**MovieLens-IMDb linking:** A small number of MovieLens `links.csv` entries point to mismatched 
IMDb IDs due to title collisions in IMDb itself (e.g., "Black Mirror" linked to an unrelated 
2011 short film instead of the 2011 TV series). These surface as NaN metadata in CF 
recommendations and are filtered out naturally by downstream `rating_normalized` checks. 
Not fixed at pipeline level — verified via manual research on a case-by-case basis.

**Content-based ranking (Stage 2):** Titles tagged with very few genres (e.g., single-tag 
"Drama") can rank exact single-tag matches above thematically-closer multi-tag titles, due 
to cosine similarity's sensitivity to tag-vector sparsity. Will be addressed by the learned 
ranking model (Stage 6) rather than hand-tuned further in the MVP.