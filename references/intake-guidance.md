# Intake Guidance

## Ask Only When Needed

Do not force a clarification turn for every request. Ask when either condition
is true:

1. The topic is too broad to produce a focused keyword set, such as "global
   economy", "stocks", "AI", or "market news".
2. The user has not indicated whether recency or a broader trend window matters,
   and choosing 7 versus 30 days could materially change the result.

## Question Template

```text
为了提高命中精度，请补充：

1. 你最关注哪个方向？例如宏观经济、股市、央行政策、行业或具体公司。
2. 搜索最近 7 天还是 30 天？

也可以回复“使用默认设置”，默认搜索最近 7 天。
```

Ask both questions in one turn. If only one item is ambiguous, ask only that
item.

## Do Not Ask

Do not ask users to choose regions, languages, channels, Shorts, advertising,
or entertainment filters unless they explicitly mention a conflicting need.

Defaults:

- priority regions: `US`, `JP`, `HK`, `GB`;
- fallback regions: `KR`, `TW`, `DE`, `FR`, `CA`;
- no language restriction;
- Shorts excluded;
- advertisements, promotions, and entertainment content excluded.
