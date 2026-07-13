# Closed Beta Checklist

## Product readiness

- [x] Strategy Engine preserved  
- [x] Portfolio / Execution Intelligence preserved  
- [x] Broker Connectivity + certification (real sessions only)  
- [x] MT5 Gateway + Cloud Gateway Manager  
- [x] Beta invite / maintenance / read-only gates  
- [x] Get Started + tour + paper tutorial + What’s New  
- [ ] Live Windows MT5 hosts registered (operator)  
- [ ] Invite codes distributed (operator)  
- [ ] Feedback webhook configured (optional)

## Safety

- [ ] `EXECUTION_ENABLED=false` in beta environments  
- [ ] No broker credentials in Railway  
- [ ] Paper-first messaging in onboarding  

## Launch day

- [ ] Tag build / update What’s New  
- [ ] Enable `NEXT_PUBLIC_BETA_MODE`  
- [ ] Smoke: login → get-started → paper → support feedback  
- [ ] Monitor `/ops` and feedback channel  

## Exit criteria (to open beta / GA)

- [ ] P0/P1 feedback closed or mitigated  
- [ ] At least one priority broker certified on live MT5  
- [ ] HA heartbeats stable for registered gateways  
- [ ] Changelog published
