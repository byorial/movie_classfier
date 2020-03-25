# movie_classfier plugin for SJVA
## 기본 기능
- SJVA의 영화처리 후 저장된 경로를 탐색하여 파일명이나 영화정보(장르, 국가, 연도, 관람등급)를 기반으로 파일 재분류
- 기초데이터는 sjva.db 의 plugin_fileprocess_movie_item 의 movie_more_info 기준

- 스케쥴러에 의한 동작 시 최근 동작한 이후 SJVA에 의해 처리된 데이터를 대상으로 함
- 1회 실행시 시간체크 무시함, SJVA에 의해 처리된 전체 데이터를 대상으로 함(이미 원본 파일/폴더가 없어진 경우 무시함)
- 테스트 실행시 시간체크 무시함, 실제 파일을 이동하지 않고 처리 결과만 

## 플러그인용 설정 샘플 - 영화정보 기반
- "[검색조건], [이동폴더명]" 형태로 지정, 항목구분은 엔터, 대소문자 구분안함
- 이동폴더명에 '/' 로 시작하는 절대경로 지정시 매칭된 영화는 해당경로로 이동
- 검색조건 변경 : AND(&), OR(|), 파일명 처리기준과 동일하게 
- ~~검색조건이 여러개인 경우 ex) 한국 멜로 영화 는 '한국|멜로'와 같이 적용-~~
- ~~검색조건을 모두 만족해야 매칭됨(무조건 AND조건)~~
- 정규표현식 적용 가능, 단, 검색조건내 구분자(|) 내 항목에만 적용
- 지정한 순서대로 매칭, 이동처리함

### 국가별로 분류 예시 
```
한국,korea
미국,usa
중국|홍콩|일본,asia
...
```
- '한국'을 포함하는 경우 korea, '미국'을 포함하는 경우 usa 폴더로 이동 
- '중국' or '홍콩' or, '일본' 을 포함하는 경우 asia 폴더로 이동 

### 연도별 분류 예시
```
198[0-9][.], 1980-1989
199[0-9][.], 1990-1999
200[0-9][.], 2000-2009
201[0-9][.], 2010-2019
```
- 10년 단위로 영화 분류, 1981년 영화는 '1980-1989'폴더로 이동
- 파일명조건과 영화정보 조건에 모두 사용할 수 있음

### 장르별/등급별 분류 예시

```
애니메이션&전체관람가, child
애니메이션&12세, child
가족&전체관람가, child
로멘스/멜로&관람불가, adult
```
- 애니메이션이나 가족영화 child 폴더로 이동
- 성인영화 (로멘스멜로 + 청소년 관람불가) adult 폴더로 이동

## 플러그인 설정용 샘플 - 파일명 기반 
- "[검색조건], [이동폴더명]" 형태로 지정, 항목구분은 엔터, 대소문자 구분안함
- 이동폴더명에 '/' 로 시작하는 절대경로 지정시 매칭된 영화는 해당경로로 이동
- 검색조건 내 '|'는 OR 조건 '&'는 AND 조건
- 정규표현식 적용 가능, 단, 검색조건내 구분자(|) 내 항목에만 적용
- 지정한 순서대로 매칭, 이동처리함

## 파일명 기반 영화 분류 예시
```
4K&REMUX|UHD&REMUX|2160p&REMUX, 4K-REMUX
REMUX, FHD-REMUX
DTS, DTS
KORDUB|DUB, DUBBING
RARBG, RARBG
201[0-9][.], 2010
```
- 파일명에 REMUX와 4K or UHD or 2160p를 포함하는 경우 '4K-REMUX' 폴더로 이동
- 파일명에 Remux를 포함하는 경우 FHD-REMUX 폴더로 이동(우선순위에 따라 4K Remux 먼저 처리)
- 파일명에 DTS를 포함하는 경우 영화는 DTS폴더로 이동 (우선순위에 따라 4K-REMUX-DTS영화는 4K-REMUX로 이동됨)
- 파일명에 Kordub, dub 포함하는 경우 'DUBBING' 폴더로 이동
- 파일명에 RARBG를 포함하는 경우 'RARBG'폴더로 이동 
- 파일명 기준으로 2010~2019를 포함하는 경우 '2010'폴더로 이동

# 정보기반 검색 문자열 분류 데이터 
## 장르 문자열 ##
SF | 가족 | 공포 | 다큐멘터리 | 드라마 | 로맨스/멜로 | 무협 | 뮤지컬 | 미스터리 | 범죄 | 서부 | 성인 | 스릴러 | 시대극 | 애니메이션 | 액션 | 어드벤처 | 전쟁 | 코미디 | 판타지

## 관람 등급 문자열 ##
12세이상관람가 | 15세이상관람가 | 전체관람가 | 청소년관람불가

## 국가 문자열 ##
네덜란드 | 노르웨이 | 뉴질랜드 | 대만 | 덴마크 | 독일 | 러시아 | 루마니아 | 마케도니아공화국 | 멕시코 | 미국 | 벨기에 | 브라질 | 서독 | 소련 | 스웨덴 | 스페인 | 싱가폴 | 아르헨티나 | 아일랜드 | 영국 | 오스트레일리아 | 이란 | 이탈리아 | 인도 | 인도네시아 | 일본 | 중국 | 칠레 | 캐나다 | 태국 | 폴란드 | 프랑스 | 핀란드 | 한국 | 홍콩
