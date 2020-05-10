=====
GOOSE
=====

GOOSE is a new privacy-first anonymous statistic collector for Gentoo
systems.  The primary aid of the project is to collect metrics
concerning installed packages and the package build environment
in order to aid developers in decision making.  Example uses include
choosing how to divide one's time between packages and monitoring
transition to new profiles.

We realize that Gentoo users are conscious of privacy concerns,
and the participation is entirely voluntary and opt-in.  At the same
time, we put our effort to ensure that the data is collected
and transmitted securely.  The reports are decomposed immediately
upon being reserved, and only individual item counts are stored
in the database.  The submissions are periodically included in bulk
in public statistics in order to avert attempts to correlate changes
in statistics with observed connections.

We cannot guarantee a perfect secrecy of the data.  A resourceful
attacker might obtain control of the server and intercept the requests.
Furthermore, even the public data might be sufficient to make general
guesses of Gentoo systems (however, it is quite possible to make such
guesses even without the data).

The project is still during its early development.  Goose represents
the server part.  There is no submission client yet, or post-processing
tools for the results.
