#!/usr/bin/env python3
import sys
import os
from scraper import collect

def main():
    print("=" * 60)
    print("🎬 영상 대본 & 리서치 자료 자동 수집기 (Video Script & Doc Collector)")
    print("=" * 60)

    # 1. 인자가 주어졌을 때
    if len(sys.argv) > 1:
        target = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"

        # 텍스트 파일(URL 여러 개)이 입력되었을 경우 일괄 처리
        if os.path.isfile(target):
            print(f"📂 파일에서 URL 목록을 읽어옵니다: {target}")
            with open(target, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            print(f"총 {len(urls)}개 URL 수집 시작...")
            for idx, url in enumerate(urls, 1):
                print(f"\n[{idx}/{len(urls)}] 처리 중: {url}")
                result = collect(url, output_dir=output_dir)
                if result.get("ok"):
                    print(f"  ✅ 성공! [{result['type']}] {result['title']}")
                    print(f"  💾 저장: {result['filepath']}")
                else:
                    print(f"  ❌ 실패: {result.get('error')}")
            print("\n🎉 모든 수집 작업이 완료되었습니다!")
            return

        # 단일 URL 입력 처리
        result = collect(target, output_dir=output_dir)
        if result.get("ok"):
            print(f"\n✅ 수집 완료!")
            print(f"📌 제목: {result['title']}")
            print(f"📁 유형: {result['type']}")
            print(f"💾 파일 저장 위치: {result['filepath']}")
            print("\n--- [미리보기] ---")
            print(result['preview'])
            print("------------------")
        else:
            print(f"\n❌ 수집 실패: {result.get('error')}")
        return

    # 2. 인자 없이 실행되었을 때: 대화형 프롬프트
    print("수집할 유튜브 영상 링크나 웹 기사/블로그 URL을 입력하세요. (종료: q)")
    while True:
        try:
            url = input("\nURL 입력 > ").strip()
            if not url:
                continue
            if url.lower() in ["q", "exit", "quit"]:
                print("수집기를 종료합니다.")
                break

            result = collect(url)
            if result.get("ok"):
                print(f"✅ 수집 성공!")
                print(f"📌 제목: {result['title']}")
                print(f"💾 저장 완료: {result['filepath']}")
                print(f"\n미리보기:\n{result['preview']}")
            else:
                print(f"❌ 실패: {result.get('error')}")
        except (KeyboardInterrupt, EOFError):
            print("\n수집기를 종료합니다.")
            break

if __name__ == "__main__":
    main()
