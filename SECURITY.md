# Security policy

## Reporting

Use GitHub private vulnerability reporting. Do not attach real radar captures,
room geometry, beacon identifiers, entity IDs, addresses, credentials, or
notification targets to a public issue.

## Deployment guidance

- Keep the atomic-frame source and Home Assistant API on a restricted network.
- Treat raw frames, completed trajectories, and O-D events as movement data.
- The local lab parses uploaded CSV data in memory and does not write it. The
  browser still sends the file to the loopback-only Python server, so do not bind
  that server to an untrusted network interface.
- Keep real configuration bundles outside public repositories.
- Do not use this experimental tracker alone for alarms, access control, or
  other safety-critical decisions.
- Keep a fallback automation path when tracking or input cadence becomes
  unhealthy.