## Metadata

* **Smell name:** Refs in Dependency Vector
* **Expected smell location:** Function `my-component`
* **Affected forms:** `r/use-effect`
* **Short explanation:** Passing a Reagent atom directly in a dependency vector doesn't trigger reactivity properly; it should be dereferenced.

```Clojure
(ns ui.dashboard
  (:require [reagent.core :as r]))

(defn dashboard []
  (let [user (r/atom {:name "Alice"})]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: r/atom passed directly as dependency
      (r/use-effect
       (fn [] (println "User changed"))
       [user])
      ; VALIDATION: SMELL END
      [:div "Hello " (:name @user)])))
```
