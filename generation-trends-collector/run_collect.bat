@echo off
set CF_API_TOKEN=HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U
set CF_ACCOUNT_ID=dddb47cb848a3a6100f19fdcd6811212
set CF_KV_NAMESPACE_ID=f5c396bf00af493abad3568261143511

cd /d "C:\Users\work\Desktop\Claudeフォルダ\AI\generation-trends-collector"
py collect_generation_trends.py
