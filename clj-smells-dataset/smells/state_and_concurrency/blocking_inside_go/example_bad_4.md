## Metadata

* **Smell name:** blocking_inside_go
* **Expected smell location:** Macro `go` in `setup-fixture`
* **Affected forms:** `go`, `<!!`
* **Short explanation:** Using a blocking `<!!` operation inside a `go` block blocks a thread from the core.async fixed thread pool, which can lead to pool starvation.

```Clojure
(ns tests.fixture.setup
  (:require [clojure.core.async :as a :refer [go <!! chan >!]]))

(defn async-db-setup []
  (let [c (chan)]
    (go (>! c :db-ready))
    c))

(defn setup-fixture
  []
  (go
    ; VALIDATION: SMELL START - blocking_inside_go
    ; VALIDATION: Using <!! blocks the go block thread
    (let [status (<!! (async-db-setup))]
    ; VALIDATION: SMELL END
      (println "Fixture setup:" status))))
```
