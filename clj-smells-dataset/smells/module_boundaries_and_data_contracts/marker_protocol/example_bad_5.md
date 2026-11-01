## Metadata

* **Smell name:** marker_protocol
* **Expected smell location:** Top-level form
* **Affected forms:** `defprotocol`
* **Short explanation:** Defining a protocol with no methods just to use it as a type marker via `satisfies?` is unidiomatic. In Clojure, metadata or sets are usually better suited for attaching markers to data.

```Clojure
(ns myapp.commands)

; VALIDATION: SMELL START - marker_protocol
; VALIDATION: empty protocol as marker
(defprotocol Command)
; VALIDATION: SMELL END

(defrecord CreateUser [name email]
  Command)
```
