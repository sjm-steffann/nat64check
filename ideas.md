To do / Ideas
=============

- Consistency in reporting
  - If no IPv6 AAAA then don't run IPv6-only test and tell user
  - If IPv6 AAAA but no website then call it broken
  - Same for NAT64

  - Range:
    - If IPv6 AAAA + ping but no website: "IPv6 web server broken"
    - If IPv6 AAAA but no ping or website: "IPv6 broken"
    - if NAT64 broken and IPv6 broken then: 'NAT64 broken because of broken IPv6'

- Allow user to create accounts
  - Upload list of URLs
  - Schedule monitoring and see progress/decline
  - Reporting

- Statistics
  - Cisco top-1m
  - Overall
  - Filter on CC-TLD etc
