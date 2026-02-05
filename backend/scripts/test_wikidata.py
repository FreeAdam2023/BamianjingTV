#!/usr/bin/env python3
"""Test Wikidata API from Python - run inside container to debug search issues"""
import asyncio
import httpx

async def test_search():
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": "New Orleans",
        "language": "en",
        "format": "json",
        "limit": 1,
    }

    print("Testing Wikidata API search...")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()

        data = response.json()
        print(f"Response JSON keys: {data.keys()}")

        results = data.get("search", [])
        print(f"Search results count: {len(results)}")

        if results:
            qid = results[0].get("id")
            label = results[0].get("label")
            print(f"✓ Found: {label} -> {qid}")
        else:
            print("✗ No results found")
            print(f"Full response: {data}")

if __name__ == "__main__":
    asyncio.run(test_search())
