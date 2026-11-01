## Metadata

* **Smell name:** nested_atoms
* **Expected smell location:** Feature flags atom
* **Affected forms:** `atom`
* **Short explanation:** Storing an atom inside another atom makes state synchronization difficult and breaks the single-source-of-truth principle.

```Clojure
(ns app.feature.flags)

(def flags-registry
  (atom {:environment "production"
         ; VALIDATION: SMELL START - nested_atoms
         ; VALIDATION: Storing an atom inside another atom
         :active-flags (atom #{:new-checkout :beta-dashboard})}))
         ; VALIDATION: SMELL END

(defn enable-flag!
  [flag-kw]
  (swap! (:active-flags @flags-registry) conj flag-kw))
```
