from __future__ import annotations


WEIGHTS = {"strategy":20,"technical":15,"market_context":15,"timeframe":10,"regime":5,"news":10,"noise":10,"risk":10,"compliance":5}


def build(*, breakout:dict, technical:dict, market_context:dict, timeframe:dict, regime:dict,
          news:dict, noise:dict, risk:dict, compliance:dict) -> dict:
    strategy_applicable=breakout.get("applicable",True)
    context_fraction=((.4 if market_context.get("complete") else 0)+(.3 if market_context.get("benchmarks_available") else 0)+(.3 if market_context.get("benchmark_support") else 0)) if strategy_applicable else 1
    technical_fraction=max(0,min(1,float(technical.get("score",0))/100)) if technical.get("passed") else 0
    fractions={"strategy":1 if breakout.get("passed") or not strategy_applicable else 0,"technical":technical_fraction,
        "market_context":context_fraction,"timeframe":1 if timeframe.get("passed") else 0,
        "regime":1 if regime.get("passed") else 0,"news":1 if news.get("passed") else 0,
        "noise":1 if noise.get("passed") else 0,"risk":1 if risk.get("passed") else 0,
        "compliance":1 if compliance.get("passed") else 0}
    components={name:{"weight":weight,"fraction":round(fractions[name],3),"points":round(weight*fractions[name],2)} for name,weight in WEIGHTS.items()}
    hard_failures=[name for name,value in fractions.items() if name!="technical" and value<1]
    total=round(sum(item["points"] for item in components.values()),2)
    return {"score":total,"maximum":100,"components":components,"hard_failures":hard_failures,
        "advisory_only":True,"reason":"Transparent evidence summary; hard gates remain authoritative."}
