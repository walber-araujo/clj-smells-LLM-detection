## Metadata

* **Smell name:** Refs in Dependency Vector
* **Expected smell location:** Function `my-component`
* **Affected forms:** `r/use-effect`
* **Short explanation:** Passing a Reagent atom directly in a dependency vector doesn't trigger reactivity properly; it should be dereferenced.

```Clojure
(ns ui.search
  (:require [reagent.core :as r]))

(defn search-bar []
  (let [query (r/atom "")]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Dependency vector contains [query] instead of [@query]
      (r/use-effect
       (fn [] (println "Searching for:" @query))
       [query])
      ; VALIDATION: SMELL END
      [:input {:on-change #(reset! query (.. % -target -value))}])))
```
