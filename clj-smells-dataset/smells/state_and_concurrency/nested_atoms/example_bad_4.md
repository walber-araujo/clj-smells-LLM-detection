## Metadata

* **Smell name:** nested_atoms
* **Expected smell location:** Cache atom
* **Affected forms:** `atom`
* **Short explanation:** Storing an atom inside another atom makes state synchronization difficult and breaks the single-source-of-truth principle.

```Clojure
(ns app.cache.memory)

; VALIDATION: SMELL START - nested_atoms
; VALIDATION: Storing an atom inside another atom
(def system-cache
  (atom {:users (atom {})
         :products (atom {})}))
; VALIDATION: SMELL END

(defn cache-user!
  [id user]
  (swap! (:users @system-cache) assoc id user))
```
