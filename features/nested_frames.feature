Feature: Multi-Level Nested Iframe Testing
@smoke
  Scenario: Interact with Parent, Child, and Deeply Nested Grandchild Iframes
    Given I navigate to the "Nested Frames" page
    Then the "Title" label should have text "Store Checkout"

    # Level 0 (Main Page)
    When I fill the "Customer" field with "Alice Johnson"
    And I click the "View Policy" button

    # Level 1 (Parent Frame)
    And I fill the "Card Number" field with "4111222233334444"
    And I click the "Validate Card" button

    # Level 2 (Child Frame)
    And I fill the "Bank Reference" field with "REF-98765"
    And I click the "Initiate Challenge" button

    # Level 3 (Deeply Nested Grandchild Frame)
    And I fill the "OTP" field with "999888"
    And After I click the "Confirm Payment" button it is disabled
    Then the "Verification Status" label should be visible
    And the "Verification Status" label should have text "Verification Success: Payment Authorized"
