## Metadata

* **Smell name:** Refs in Dependency Vector
* **Expected smell location:** Function `my-component`
* **Affected forms:** `r/use-effect`
* **Short explanation:** Passing a Reagent atom directly in a dependency vector doesn't trigger reactivity properly; it should be dereferenced.

```Clojure
(ns ui.counter
  (:require [reagent.core :as r]))

(defn counter-widget []
  (let [timer (r/atom 0)]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Using atom reference as dependency instead of value
      (r/use-effect
       (fn [] (println "Timer tick"))
       [timer])
      ; VALIDATION: SMELL END
      [:div @timer])))
```
