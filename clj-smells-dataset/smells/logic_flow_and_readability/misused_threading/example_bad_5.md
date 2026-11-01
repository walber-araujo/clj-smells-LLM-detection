## Metadata

* **Smell name:** misused_threading
* **Expected smell location:** Function `load-system-config`
* **Affected forms:** `->`
* **Short explanation:** Mixes IO, parsing, and deep map extraction in a single threading macro, confusing the primary abstraction level.

```Clojure
(ns system.core
  (:require [aero.core :as aero]))

(defn load-system-config [env]
  ; VALIDATION: SMELL START - misused_threading
  ; VALIDATION: Mixes IO/parsing (aero/read-config) with map lookups in a confusing way
  (-> "config.edn"
      clojure.java.io/resource
      (aero/read-config {:profile env})
      :database
      :password
      encrypt-secret))
  ; VALIDATION: SMELL END
```
