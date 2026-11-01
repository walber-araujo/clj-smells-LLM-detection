## Metadata

* **Smell name:** Refs in Dependency Vector
* **Expected smell location:** Function `my-component`
* **Affected forms:** `r/use-effect`
* **Short explanation:** Passing a Reagent atom directly in a dependency vector doesn't trigger reactivity properly; it should be dereferenced.

```Clojure
(ns ui.component
  (:require [reagent.core :as r]))

(defn my-component []
  (let [count-state (r/atom 0)]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Using Reagent atom in dependency vector without dereferencing
      (r/use-effect
       (fn [] (println "Count changed"))
       [count-state])
      ; VALIDATION: SMELL END
      [:div "Count: " @count-state])))
```
